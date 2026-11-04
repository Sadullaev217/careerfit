import json
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Protocol

from app.job_sources import JobProvider, Posting

MAX_POSTING_AGE_DAYS = 60
UPSERT_BATCH = 1000
TITLES_PER_OCCUPATION = 15
OCCUPATION_MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "noc_esco_map.json"


class MarketStore(Protocol):
    def upsert_postings(self, rows: list[dict[str, Any]]) -> None: ...
    def delete_postings_before(self, cutoff: date) -> None: ...
    def upsert_occupations(self, rows: list[dict[str, Any]]) -> None: ...
    def upsert_occupation_titles(self, rows: list[dict[str, Any]]) -> None: ...


@dataclass(frozen=True)
class RefreshSummary:
    fetched: int
    too_old: int
    duplicates: int
    stored: int
    occupations: int


def select_postings(postings: Iterable[Posting], today: date) -> tuple[list[Posting], int, int, int]:
    """One copy per ad per region: the region's figures stay right, and national stats dedupe further."""
    cutoff = today - timedelta(days=MAX_POSTING_AGE_DAYS)
    kept: dict[tuple[str, str], Posting] = {}
    fetched = too_old = duplicates = 0
    for posting in postings:
        fetched += 1
        if posting.posted_on < cutoff:
            too_old += 1
            continue
        key = (posting.duplicate_key, posting.region)
        if key in kept:
            duplicates += 1
        else:
            kept[key] = posting
    return list(kept.values()), fetched, too_old, duplicates


def posting_row(posting: Posting) -> dict[str, Any]:
    return {
        "source": posting.source,
        "source_id": posting.source_id,
        "title": posting.title,
        "original_title": posting.original_title,
        "occupation_code": posting.occupation_code,
        "occupation_name": posting.occupation_name,
        "region": posting.region,
        "economic_region": posting.economic_region,
        "city": posting.city,
        "posted_at": posting.posted_on.isoformat(),
        "vacancies": posting.vacancies,
        "education_level": posting.education_level,
        "experience_level": posting.experience_level,
        "employment_type": posting.employment_type,
        "salary_min": posting.salary_annual_min,
        "salary_max": posting.salary_annual_max,
        "salary_currency": posting.salary_currency,
        "duplicate_key": posting.duplicate_key,
    }


def load_occupation_map(path: Path = OCCUPATION_MAP_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["code"]: row for row in json.loads(path.read_text(encoding="utf-8"))}


def occupation_rows(
    postings: Sequence[Posting], occupation_map: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    names = {posting.occupation_code: posting.occupation_name for posting in postings}
    return [
        {
            "code": code,
            "name": name,
            "esco_uri": occupation_map.get(code, {}).get("esco_uri"),
            "esco_title": occupation_map.get(code, {}).get("esco_title"),
        }
        for code, name in names.items()
    ]


def title_rows(
    postings: Sequence[Posting], embed: Callable[[Sequence[str]], list[list[float]]]
) -> list[dict[str, Any]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    seen: set[str] = set()
    for posting in postings:
        if posting.duplicate_key not in seen:
            seen.add(posting.duplicate_key)
            counts[posting.occupation_code][posting.title] += 1
    rows: list[dict[str, Any]] = [
        {"title": title, "occupation_code": code, "posting_count": total}
        for code, titles in counts.items()
        for title, total in titles.most_common(TITLES_PER_OCCUPATION)
    ]
    if not rows:
        return []
    vectors = embed([row["title"] for row in rows])
    return [{**row, "embedding": vector} for row, vector in zip(rows, vectors, strict=True)]


def _in_batches(rows: list[dict[str, Any]], store_batch: Callable[[list[dict[str, Any]]], None]) -> None:
    for start in range(0, len(rows), UPSERT_BATCH):
        store_batch(rows[start : start + UPSERT_BATCH])


def refresh_market_data(
    provider: JobProvider,
    store: MarketStore,
    embed: Callable[[Sequence[str]], list[list[float]]],
    today: date | None = None,
) -> RefreshSummary:
    today = today or date.today()
    postings, fetched, too_old, duplicates = select_postings(provider.fetch(), today)
    occupations = occupation_rows(postings, load_occupation_map())
    # Occupations go first because titles reference them.
    _in_batches(occupations, store.upsert_occupations)
    _in_batches(title_rows(postings, embed), store.upsert_occupation_titles)
    _in_batches([posting_row(posting) for posting in postings], store.upsert_postings)
    store.delete_postings_before(today - timedelta(days=MAX_POSTING_AGE_DAYS))
    return RefreshSummary(fetched, too_old, duplicates, len(postings), len(occupations))
