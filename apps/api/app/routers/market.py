from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app import embeddings, store
from app.auth import CurrentUser, get_current_user
from app.skill_matching import shares_a_word

router = APIRouter(prefix="/market")

User = Annotated[CurrentUser, Depends(get_current_user)]

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
MIN_REGIONAL_SALARY_SAMPLE = 10
MEDIUM_CONFIDENCE_SAMPLE = 30
HIGH_CONFIDENCE_SAMPLE = 100
CONCENTRATED_PAY_SHARE = 0.5
TOP_REQUIRED_SKILLS = 15
TOP_PREFERRED_SKILLS = 10

SOURCES = [
    "Contains information licensed under the Open Government Licence – Canada.",
    "Skills from ESCO, the European Commission's classification of skills and occupations.",
]
LIMITATIONS = (
    "Pay comes from ads on Canada's Job Bank, which doesn't include every job, so actual pay may "
    "differ. Skills are the official list for this occupation, not a count of what employers are "
    "asking for right now."
)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SalaryRange(CamelModel):
    p25: float
    median: float
    p75: float
    currency: str
    period: str
    sample_size: int
    region: str
    confidence: str
    concentrated: bool


class MarketRequirements(CamelModel):
    role: str
    matched_title: str
    occupation_code: str
    occupation_name: str
    region: str
    sample_size: int
    salary: SalaryRange | None
    required_skills: list[str]
    preferred_skills: list[str]
    education: dict[str, int]
    experience: dict[str, int]
    latest_posting: str | None
    sources: list[str]
    limitations: str


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})


def _resolve_region(region: str | None) -> str | None:
    if region is None or region.strip().lower() in ("", "canada", "ca"):
        return None
    resolved = REGIONS.get(region.strip().lower())
    if resolved is None:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown_region",
            "Choose a Canadian province or territory, or Canada.",
        )
    return resolved


def _confidence(sample_size: int) -> str:
    if sample_size >= HIGH_CONFIDENCE_SAMPLE:
        return "high"
    return "medium" if sample_size >= MEDIUM_CONFIDENCE_SAMPLE else "low"


def _resolve_occupation(role: str) -> dict[str, Any]:
    match = store.match_occupation(embeddings.embed_texts([role])[0])
    if (
        match is None
        or match["similarity"] < MIN_ROLE_SIMILARITY
        or not (
            shares_a_word(role, match["title"]) or shares_a_word(role, match["occupation_name"])
        )
    ):
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "role_not_found",
            "We couldn't recognise this role. Try a common job title, like \"accountant\".",
        )
    return match


def _salary(stats: dict[str, Any], region: str) -> SalaryRange | None:
    size = stats["salary_sample_size"]
    if not size:
        return None
    # The data names no employers, so one pay scale can fill a whole sample.
    concentrated = (stats.get("salary_top_share") or 0) > CONCENTRATED_PAY_SHARE
    return SalaryRange(
        p25=round(stats["salary_p25"]),
        median=round(stats["salary_median"]),
        p75=round(stats["salary_p75"]),
        currency="CAD",
        period="yearly",
        sample_size=size,
        region=region,
        confidence="low" if concentrated else _confidence(size),
        concentrated=concentrated,
    )


@router.get("/requirements", response_model=MarketRequirements)
def market_requirements(
    _user: User,
    role: Annotated[str, Query(min_length=2, max_length=200)],
    region: Annotated[str | None, Query(max_length=60)] = None,
) -> MarketRequirements:
    province = _resolve_region(region)
    match = _resolve_occupation(role.strip())
    code = match["occupation_code"]

    stats = store.market_stats(code, province)
    salary = _salary(stats, province or NATIONAL)
    # A handful of ads can't describe a province, so say plainly that the figure is national.
    if province and stats["salary_sample_size"] < MIN_REGIONAL_SALARY_SAMPLE:
        salary = _salary(store.market_stats(code, None), NATIONAL)

    skills = store.occupation_skills(code)
    required = [row["skills"]["name"] for row in skills if row["required"]]
    preferred = [row["skills"]["name"] for row in skills if not row["required"]]

    return MarketRequirements(
        role=role.strip(),
        matched_title=match["title"],
        occupation_code=code,
        occupation_name=match["occupation_name"],
        region=province or NATIONAL,
        sample_size=stats["sample_size"],
        salary=salary,
        required_skills=required[:TOP_REQUIRED_SKILLS],
        preferred_skills=preferred[:TOP_PREFERRED_SKILLS],
        education=stats["education"],
        experience=stats["experience"],
        latest_posting=stats["latest_posting"],
        sources=SOURCES,
        limitations=LIMITATIONS,
    )
