"""Job market sources. A new country or provider is one more class with a fetch method."""

import csv
import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol
from urllib.parse import urljoin, urlsplit

import httpx

JOB_BANK_DATASET_ID = "ea639e28-c0fc-48bf-b5dd-b8899bd43072"
JOB_BANK_API = "https://open.canada.ca/data/api/3/action/package_show"
# The portal hands downloads over to the government's own Azure storage.
JOB_BANK_HOSTS = {"open.canada.ca", "opencanada.blob.core.windows.net"}
JOB_BANK_FILES_PER_REFRESH = 3
MAX_DOWNLOAD_BYTES = 300 * 1024 * 1024
MAX_REDIRECTS = 3

# Hourly pay is shown as a full-time yearly figure, so part-time jobs stay comparable.
ANNUAL_FACTORS = {"Hour": 2080, "Day": 260, "Week": 52, "Bi-weekly": 26, "Month": 12, "Year": 1}
# The data has entry errors: one salary works out to $386 million a year, and 43 software ads say
# "$101 daily". Full-time at Canada's lowest minimum wages is about $31,000, hence the floor.
MIN_PLAUSIBLE_ANNUAL = 30_000
MAX_PLAUSIBLE_ANNUAL = 500_000
_MISSING_VALUES = {"", "na", "*no data", "n/a"}


class SourceError(Exception):
    pass


@dataclass(frozen=True)
class Posting:
    source: str
    source_id: str
    title: str
    original_title: str | None
    occupation_code: str
    occupation_name: str
    region: str
    economic_region: str | None
    city: str | None
    posted_on: date
    vacancies: int
    education_level: str | None
    experience_level: str | None
    employment_type: str | None
    salary_annual_min: float | None
    salary_annual_max: float | None
    salary_currency: str
    duplicate_key: str


class JobProvider(Protocol):
    def fetch(self) -> Iterator[Posting]: ...


def _clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return None if text.lower() in _MISSING_VALUES else text


def annualize(amount: str | None, per: str | None) -> float | None:
    factor = ANNUAL_FACTORS.get((per or "").strip())
    try:
        value = float(amount or "")
    except ValueError:
        return None
    if factor is None:
        return None
    annual = value * factor
    return round(annual, 2) if MIN_PLAUSIBLE_ANNUAL <= annual <= MAX_PLAUSIBLE_ANNUAL else None


def _duplicate_key(*parts: Any) -> str:
    """Some ads repeat across hundreds of towns: one appears 938 times in a single month."""
    joined = "|".join(str(part or "").strip().lower() for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def parse_job_bank(raw: bytes) -> Iterator[Posting]:
    lines = raw.decode("utf-16").splitlines()
    for row in csv.DictReader(lines, delimiter="\t"):
        code = _clean(row.get("NOC21 Code"))
        name = _clean(row.get("NOC21 Code Name"))
        source_id = _clean(row.get("WIC Job Location Snapshot ID"))
        title = _clean(row.get("Job Title"))
        province = _clean(row.get("Province/Territory"))
        posted = _clean(row.get("First Posting Date"))
        if not (code and name and source_id and title and province and posted):
            continue
        try:
            posted_on = datetime.strptime(posted, "%Y/%m/%d").date()
        except ValueError:
            continue

        per = row.get("Salary Per")
        low = annualize(row.get("Salary Minimum"), per)
        high = annualize(row.get("Salary Maximum"), per)
        original = _clean(row.get("Original Job Title"))
        try:
            vacancies = max(int(row.get("Vacancy Count") or 1), 1)
        except ValueError:
            vacancies = 1

        yield Posting(
            source="job_bank",
            source_id=source_id,
            title=title,
            original_title=original,
            occupation_code=code,
            occupation_name=name,
            region=province,
            economic_region=_clean(row.get("Economic  Region")),
            city=_clean(row.get("City")),
            posted_on=posted_on,
            vacancies=vacancies,
            education_level=_clean(row.get("Education LOS")),
            experience_level=_clean(row.get("Experience Level")),
            employment_type=_clean(row.get("Employment Type")),
            salary_annual_min=low,
            salary_annual_max=high if high is not None else low,
            salary_currency="CAD",
            duplicate_key=_duplicate_key(
                code, title, original, row.get("Salary Minimum"), row.get("Salary Maximum"), posted
            ),
        )


def newest_english_files(package: dict[str, Any], count: int) -> list[str]:
    files = [
        resource
        for resource in package["resources"]
        if resource.get("format") == "CSV" and "en" in (resource.get("language") or [])
    ]
    files.sort(key=lambda resource: resource.get("created") or "", reverse=True)
    return [resource["url"] for resource in files[:count]]


def _require_official_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in JOB_BANK_HOSTS:
        raise SourceError("Job Bank pointed at an unexpected host")


class JobBankProvider:
    """Canada's Job Bank open data, under the Open Government Licence - Canada, which allows
    commercial use. It has salary, occupation and location but no job descriptions or skills."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=300, trust_env=False)

    def _download(self, url: str) -> bytes:
        for _ in range(MAX_REDIRECTS + 1):
            _require_official_host(url)
            with self._client.stream("GET", url, follow_redirects=False) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_DOWNLOAD_BYTES:
                        raise SourceError("Job Bank file is larger than expected")
                return bytes(data)
        raise SourceError("Job Bank file redirected too many times")

    def fetch(self) -> Iterator[Posting]:
        response = self._client.get(JOB_BANK_API, params={"id": JOB_BANK_DATASET_ID})
        response.raise_for_status()
        package = response.json()["result"]
        for url in newest_english_files(package, JOB_BANK_FILES_PER_REFRESH):
            yield from parse_job_bank(self._download(url))
