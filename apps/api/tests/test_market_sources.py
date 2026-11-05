from datetime import date

import httpx
import pytest

from app import tasks
from app.celery_app import celery_app
from app.job_sources import (
    MAX_PLAUSIBLE_ANNUAL,
    JobBankProvider,
    SourceError,
    annualize,
    newest_english_files,
    parse_job_bank,
)
from app.market_data import (
    MAX_POSTING_AGE_DAYS,
    TITLES_PER_OCCUPATION,
    occupation_rows,
    posting_row,
    refresh_market_data,
    select_postings,
    title_rows,
)

COLUMNS = [
    "WIC Job Location Snapshot ID", "Job Title", "Original Job Title", "NOC21 Code", "NOC21 Code Name",
    "First Posting Date", "Vacancy Count", "Education LOS", "Experience Level", "Province/Territory",
    "City", "Economic  Region", "Employment Type", "Salary Per", "Salary Minimum", "Salary Maximum",
]  # fmt: skip


def row(**overrides: str) -> dict[str, str]:
    return {
        "WIC Job Location Snapshot ID": "1",
        "Job Title": "cook",
        "Original Job Title": "NA",
        "NOC21 Code": "63200",
        "NOC21 Code Name": "Cooks",
        "First Posting Date": "2026/10/15",
        "Vacancy Count": "2",
        "Education LOS": "Secondary (high) school graduation certificate",
        "Experience Level": "NA",
        "Province/Territory": "Ontario",
        "City": "Toronto",
        "Economic  Region": "Toronto Region",
        "Employment Type": "Full time",
        "Salary Per": "Hour",
        "Salary Minimum": "20",
        "Salary Maximum": "25",
        **overrides,
    }


def job_bank_file(*rows: dict[str, str]) -> bytes:
    lines = ["\t".join(COLUMNS), *("\t".join(r[c] for c in COLUMNS) for r in rows)]
    return "\n".join(lines).encode("utf-16")


def parsed(*rows: dict[str, str]) -> list:
    return list(parse_job_bank(job_bank_file(*rows)))


@pytest.mark.parametrize(
    ("amount", "per", "expected"),
    [
        ("20", "Hour", 41_600),
        ("80000", "Year", 80_000),
        ("5000", "Month", 60_000),
        ("1000", "Week", 52_000),
        ("2000", "Bi-weekly", 52_000),
        ("200", "Day", 52_000),
    ],
)
def test_pay_periods_become_yearly_amounts(amount: str, per: str, expected: float) -> None:
    assert annualize(amount, per) == expected


@pytest.mark.parametrize(
    ("amount", "per"),
    [
        ("185640", "Hour"),  # a yearly figure entered as hourly gives $386 million
        ("101", "Day"),  # an hourly rate entered as daily gives $26,260
        ("21", "Year"),  # "$21.00 to $23.00 annually"
        ("10000", "Year"),
        ("", "Hour"),
        ("abc", "Hour"),
        ("20", "NA"),
        ("20", "Fortnight"),
    ],
)
def test_implausible_or_missing_pay_is_dropped(amount: str, per: str) -> None:
    assert annualize(amount, per) is None


def test_top_of_the_plausible_range_is_kept() -> None:
    assert annualize(str(MAX_PLAUSIBLE_ANNUAL), "Year") == MAX_PLAUSIBLE_ANNUAL


def test_parses_a_posting() -> None:
    posting = parsed(row())[0]
    assert posting.occupation_code == "63200"
    assert posting.region == "Ontario"
    assert posting.posted_on == date(2026, 10, 15)
    assert posting.vacancies == 2
    assert (posting.salary_annual_min, posting.salary_annual_max) == (41_600, 52_000)
    assert posting.salary_currency == "CAD"
    assert posting.experience_level is None
    assert posting.original_title is None
    assert posting.education_level.startswith("Secondary")


@pytest.mark.parametrize(
    "missing",
    ["NOC21 Code", "NOC21 Code Name", "Job Title", "Province/Territory", "First Posting Date"],
)
def test_rows_missing_essentials_are_skipped(missing: str) -> None:
    assert parsed(row(**{missing: "NA"})) == []


def test_unreadable_date_is_skipped() -> None:
    assert parsed(row(**{"First Posting Date": "soon"})) == []


def test_missing_top_of_range_uses_the_bottom() -> None:
    posting = parsed(row(**{"Salary Maximum": "NA"}))[0]
    assert posting.salary_annual_max == posting.salary_annual_min


def test_same_ad_in_different_towns_shares_a_key() -> None:
    a, b = parsed(row(), row(**{"WIC Job Location Snapshot ID": "2", "City": "Ottawa"}))
    assert a.duplicate_key == b.duplicate_key


def test_different_pay_is_a_different_ad() -> None:
    a, b = parsed(row(), row(**{"WIC Job Location Snapshot ID": "2", "Salary Minimum": "21"}))
    assert a.duplicate_key != b.duplicate_key


TODAY = date(2026, 11, 5)


def test_spam_repeated_in_one_province_is_kept_once() -> None:
    repeats = [row(**{"WIC Job Location Snapshot ID": str(i)}) for i in range(938)]
    kept, fetched, too_old, duplicates = select_postings(parsed(*repeats), TODAY)
    assert (len(kept), fetched, too_old, duplicates) == (1, 938, 0, 937)


def test_same_ad_is_kept_once_per_province() -> None:
    rows = [
        row(),
        row(**{"WIC Job Location Snapshot ID": "2", "City": "Ottawa"}),
        row(**{"WIC Job Location Snapshot ID": "3", "Province/Territory": "Alberta"}),
    ]
    kept, *_ = select_postings(parsed(*rows), TODAY)
    assert sorted(posting.region for posting in kept) == ["Alberta", "Ontario"]


def test_postings_over_the_age_limit_are_dropped() -> None:
    old = row(**{"First Posting Date": "2026/08/01"})
    edge = row(
        **{"WIC Job Location Snapshot ID": "2", "First Posting Date": f"2026/09/{36 - 0 - 30:02d}"}
    )
    kept, _, too_old, _ = select_postings(parsed(old, edge), TODAY)
    assert too_old == 1
    assert (TODAY - kept[0].posted_on).days <= MAX_POSTING_AGE_DAYS


def test_rows_use_the_database_column_names() -> None:
    stored = posting_row(parsed(row())[0])
    assert stored["salary_min"] == 41_600
    assert stored["posted_at"] == "2026-10-15"
    assert stored["region"] == "Ontario"


def test_occupations_take_their_links_from_the_map() -> None:
    occupation_map = {"63200": {"esco_uri": "esco/cook", "esco_title": "cook"}}
    rows = occupation_rows(parsed(row()), occupation_map)
    assert rows == [{"code": "63200", "name": "Cooks", "esco_uri": "esco/cook", "esco_title": "cook"}]


def test_occupation_without_a_link_stores_nothing_for_it() -> None:
    assert occupation_rows(parsed(row()), {})[0]["esco_uri"] is None


def fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.5] for _ in texts]


def test_spam_cannot_decide_common_titles() -> None:
    spam = [
        row(**{"WIC Job Location Snapshot ID": str(i), "Job Title": "inside sales representative"})
        for i in range(50)
    ]
    real = [
        row(**{"WIC Job Location Snapshot ID": f"r{i}", "Job Title": "cashier", "Salary Minimum": str(20 + i)})
        for i in range(3)
    ]
    rows = {r["title"]: r["posting_count"] for r in title_rows(parsed(*spam, *real), fake_embed)}
    assert rows == {"inside sales representative": 1, "cashier": 3}


def test_titles_per_occupation_are_capped() -> None:
    many = [
        row(**{"WIC Job Location Snapshot ID": str(i), "Job Title": f"title {i}"})
        for i in range(TITLES_PER_OCCUPATION + 5)
    ]
    assert len(title_rows(parsed(*many), fake_embed)) == TITLES_PER_OCCUPATION


class FakeMarketStore:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.postings: list[dict] = []
        self.cutoff: date | None = None

    def upsert_occupations(self, rows: list[dict]) -> None:
        self.calls.append("occupations")

    def upsert_occupation_titles(self, rows: list[dict]) -> None:
        self.calls.append("titles")

    def upsert_postings(self, rows: list[dict]) -> None:
        self.calls.append("postings")
        self.postings += rows

    def delete_postings_before(self, cutoff: date) -> None:
        self.calls.append("delete")
        self.cutoff = cutoff


class FakeProvider:
    def __init__(self, *rows: dict[str, str]) -> None:
        self.rows = rows

    def fetch(self):
        return iter(parsed(*self.rows))


def test_refresh_stores_in_dependency_order_then_removes_old_postings() -> None:
    store = FakeMarketStore()
    provider = FakeProvider(row(), row(**{"WIC Job Location Snapshot ID": "2"}))
    summary = refresh_market_data(provider, store, fake_embed, today=TODAY)

    assert store.calls == ["occupations", "titles", "postings", "delete"]
    assert len(store.postings) == 1
    assert (summary.fetched, summary.duplicates, summary.stored, summary.occupations) == (2, 1, 1, 1)
    assert (TODAY - store.cutoff).days == MAX_POSTING_AGE_DAYS


def test_market_refresh_is_scheduled() -> None:
    entry = celery_app.conf.beat_schedule["refresh-market-data"]
    assert entry["task"] == "refresh_market_data"
    assert entry["task"] in celery_app.tasks


def test_scheduled_task_runs_the_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_refresh(*_args: object) -> str:
        calls.append("refreshed")
        return "summary"

    monkeypatch.setattr(tasks, "refresh_market_data", fake_refresh)
    monkeypatch.setattr(tasks, "JobBankProvider", lambda: "provider")
    tasks.refresh_market_data_task.apply()
    assert calls == ["refreshed"]


def test_scheduled_task_retries_when_the_source_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def failing_refresh(*_args: object) -> str:
        calls.append("tried")
        raise httpx.ConnectError("source down")

    monkeypatch.setattr(tasks, "refresh_market_data", failing_refresh)
    monkeypatch.setattr(tasks, "JobBankProvider", lambda: "provider")
    tasks.refresh_market_data_task.apply()
    assert len(calls) == tasks.refresh_market_data_task.max_retries + 1


def test_refresh_is_safe_with_no_data() -> None:
    store = FakeMarketStore()
    summary = refresh_market_data(FakeProvider(), store, fake_embed, today=TODAY)
    assert summary.stored == 0
    assert store.calls == ["delete"]


PACKAGE = {
    "resources": [
        {"format": "CSV", "language": ["en"], "created": "2026-09-08", "url": "https://x/aug"},
        {"format": "CSV", "language": ["fr"], "created": "2026-11-04", "url": "https://x/oct-fr"},
        {"format": "CSV", "language": ["en"], "created": "2026-11-04", "url": "https://x/oct"},
        {"format": "CSV", "language": ["en"], "created": "2026-10-02", "url": "https://x/sep"},
        {"format": "PDF", "language": ["en"], "created": "2026-11-05", "url": "https://x/doc"},
    ]
}


def test_picks_the_newest_english_csv_files() -> None:
    assert newest_english_files(PACKAGE, 2) == ["https://x/oct", "https://x/sep"]


def provider_with(handler) -> JobBankProvider:
    return JobBankProvider(httpx.Client(transport=httpx.MockTransport(handler)))


FILE_URL = "https://open.canada.ca/data/dataset/x/download/file.csv"


def package_response(url: str = FILE_URL) -> httpx.Response:
    return httpx.Response(
        200, json={"result": {"resources": [{"format": "CSV", "language": ["en"], "created": "1", "url": url}]}}
    )


def test_follows_the_redirect_to_official_storage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return package_response()
        if request.url.host == "open.canada.ca":
            return httpx.Response(302, headers={"location": "https://opencanada.blob.core.windows.net/f.csv?sig=x"})
        return httpx.Response(200, content=job_bank_file(row()))

    assert len(list(provider_with(handler).fetch())) == 1


def test_refuses_a_listed_file_on_another_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return package_response("https://evil.example/file.csv")

    with pytest.raises(SourceError):
        list(provider_with(handler).fetch())


def test_refuses_a_redirect_to_another_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return package_response()
        return httpx.Response(302, headers={"location": "https://evil.example/file.csv"})

    with pytest.raises(SourceError):
        list(provider_with(handler).fetch())


def test_refuses_plain_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return package_response("http://open.canada.ca/file.csv")

    with pytest.raises(SourceError):
        list(provider_with(handler).fetch())


def test_stops_on_a_redirect_loop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return package_response()
        return httpx.Response(302, headers={"location": FILE_URL})

    with pytest.raises(SourceError):
        list(provider_with(handler).fetch())


def test_refuses_a_huge_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.job_sources.MAX_DOWNLOAD_BYTES", 10)

    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return package_response()
        return httpx.Response(200, content=b"x" * 11)

    with pytest.raises(SourceError):
        list(provider_with(handler).fetch())
