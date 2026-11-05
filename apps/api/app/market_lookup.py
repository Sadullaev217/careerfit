"""Turns a typed role and region into an occupation and pay figures, for lookups and scoring."""

import re
from typing import Any, Protocol

from app import embeddings
from app.skill_matching import shares_a_word

NATIONAL = "Canada"
REGIONS = {
    "ab": "Alberta", "alberta": "Alberta",
    "bc": "British Columbia", "british columbia": "British Columbia",
    "mb": "Manitoba", "manitoba": "Manitoba",
    "nb": "New Brunswick", "new brunswick": "New Brunswick",
    "nl": "Newfoundland and Labrador", "newfoundland and labrador": "Newfoundland and Labrador",
    "ns": "Nova Scotia", "nova scotia": "Nova Scotia",
    "nt": "Northwest Territories", "northwest territories": "Northwest Territories",
    "nu": "Nunavut", "nunavut": "Nunavut",
    "on": "Ontario", "ontario": "Ontario",
    "pe": "Prince Edward Island", "prince edward island": "Prince Edward Island",
    "qc": "Québec", "quebec": "Québec", "québec": "Québec",
    "sk": "Saskatchewan", "saskatchewan": "Saskatchewan",
    "yt": "Yukon", "yukon": "Yukon",
}  # fmt: skip
MIN_ROLE_SIMILARITY = 0.75
MIN_ROLE_SUGGESTION_SIMILARITY = 0.6
MIN_ROLE_QUERY_LENGTH = 2
MAX_ROLE_SUGGESTIONS = 8
MIN_REGIONAL_SALARY_SAMPLE = 10
MIN_ADS_STATING_REQUIREMENTS = 5
MEDIUM_CONFIDENCE_SAMPLE = 30
HIGH_CONFIDENCE_SAMPLE = 100
CONCENTRATED_PAY_SHARE = 0.5
TOP_REQUIRED_SKILLS = 15
TOP_PREFERRED_SKILLS = 10
UNKNOWN_REGION_MESSAGE = "Choose a Canadian province or territory, or Canada."
ROLE_NOT_FOUND_MESSAGE = 'We couldn\'t recognise this role. Try a common job title, like "accountant".'


class UnknownRegion(Exception):
    pass


class RoleNotFound(Exception):
    pass


class OccupationIndex(Protocol):
    def match_occupation(self, embedding: list[float]) -> dict[str, Any] | None: ...


class RoleSearch(Protocol):
    def search_occupation_titles(self, query: str, count: int) -> list[dict[str, Any]]: ...
    def match_occupations(self, embedding: list[float], count: int) -> list[dict[str, Any]]: ...


class StatsSource(Protocol):
    def market_stats(self, occupation_code: str, region: str | None) -> dict[str, Any]: ...


def resolve_region(region: str | None) -> str | None:
    if region is None or region.strip().lower() in ("", "canada", "ca"):
        return None
    resolved = REGIONS.get(region.strip().lower())
    if resolved is None:
        raise UnknownRegion
    return resolved


def resolve_occupation(role: str, index: OccupationIndex) -> dict[str, Any]:
    match = index.match_occupation(embeddings.embed_texts([role])[0])
    if (
        match is None
        or match["similarity"] < MIN_ROLE_SIMILARITY
        or not (
            shares_a_word(role, match["title"]) or shares_a_word(role, match["occupation_name"])
        )
    ):
        raise RoleNotFound
    return match


def suggest_roles(query: str, source: RoleSearch) -> list[dict[str, Any]]:
    cleaned = " ".join(re.sub(r"[^\w\s-]", " ", query).split())
    if len(cleaned) < MIN_ROLE_QUERY_LENGTH:
        return []
    found = source.search_occupation_titles(cleaned, MAX_ROLE_SUGGESTIONS)
    if found:
        return found
    # Titles are in English, so a Russian search has to go by meaning instead of by spelling.
    nearest = source.match_occupations(embeddings.embed_texts([cleaned])[0], MAX_ROLE_SUGGESTIONS)
    return [
        {
            "title": row["occupation_name"],
            "occupation_code": row["occupation_code"],
            "occupation_name": row["occupation_name"],
        }
        for row in nearest
        if row["similarity"] >= MIN_ROLE_SUGGESTION_SIMILARITY
    ]


def top_skills(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    required = [row["skills"]["name"] for row in rows if row["required"]]
    preferred = [row["skills"]["name"] for row in rows if not row["required"]]
    return required[:TOP_REQUIRED_SKILLS], preferred[:TOP_PREFERRED_SKILLS]


def requirements(
    occupation_code: str, region: str | None, stats: dict[str, Any], source: StatsSource
) -> tuple[dict[str, int], dict[str, int], bool]:
    """Education and experience wanted, from all of Canada where too few local ads state them.

    Leaving them out instead would change a score just because of where someone lives.
    """
    education, experience = stats["education"], stats["experience"]
    enough = MIN_ADS_STATING_REQUIREMENTS
    if not region or (sum(education.values()) >= enough and sum(experience.values()) >= enough):
        return education, experience, False
    national = source.market_stats(occupation_code, None)
    if sum(education.values()) < enough:
        education = national["education"]
    if sum(experience.values()) < enough:
        experience = national["experience"]
    return education, experience, True


def _confidence(sample_size: int) -> str:
    if sample_size >= HIGH_CONFIDENCE_SAMPLE:
        return "high"
    return "medium" if sample_size >= MEDIUM_CONFIDENCE_SAMPLE else "low"


def _salary_from_stats(stats: dict[str, Any], region: str) -> dict[str, Any] | None:
    size = stats["salary_sample_size"]
    if not size:
        return None
    # The data names no employers, so one pay scale can fill a whole sample.
    concentrated = (stats.get("salary_top_share") or 0) > CONCENTRATED_PAY_SHARE
    return {
        "p25": round(stats["salary_p25"]),
        "median": round(stats["salary_median"]),
        "p75": round(stats["salary_p75"]),
        "currency": "CAD",
        "period": "yearly",
        "sample_size": size,
        "region": region,
        "confidence": "low" if concentrated else _confidence(size),
        "concentrated": concentrated,
    }


def salary_range(
    occupation_code: str, region: str | None, stats: dict[str, Any], source: StatsSource
) -> dict[str, Any] | None:
    # A handful of ads can't describe a province, so the figure falls back to national and says so.
    if region and stats["salary_sample_size"] < MIN_REGIONAL_SALARY_SAMPLE:
        return _salary_from_stats(source.market_stats(occupation_code, None), NATIONAL)
    return _salary_from_stats(stats, region or NATIONAL)
