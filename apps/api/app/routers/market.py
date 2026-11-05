from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app import market_lookup, store
from app.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/market")

User = Annotated[CurrentUser, Depends(get_current_user)]

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


@router.get("/requirements", response_model=MarketRequirements)
def market_requirements(
    _user: User,
    role: Annotated[str, Query(min_length=2, max_length=200)],
    region: Annotated[str | None, Query(max_length=60)] = None,
) -> MarketRequirements:
    try:
        province = market_lookup.resolve_region(region)
        match = market_lookup.resolve_occupation(role.strip(), store)
    except market_lookup.UnknownRegion:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown_region",
            market_lookup.UNKNOWN_REGION_MESSAGE,
        ) from None
    except market_lookup.RoleNotFound:
        raise _error(
            status.HTTP_404_NOT_FOUND, "role_not_found", market_lookup.ROLE_NOT_FOUND_MESSAGE
        ) from None
    code = match["occupation_code"]

    stats = store.market_stats(code, province)
    salary = market_lookup.salary_range(code, province, stats, store)
    required, preferred = market_lookup.top_skills(store.occupation_skills(code))

    return MarketRequirements(
        role=role.strip(),
        matched_title=match["title"],
        occupation_code=code,
        occupation_name=match["occupation_name"],
        region=province or market_lookup.NATIONAL,
        sample_size=stats["sample_size"],
        salary=SalaryRange.model_validate(salary) if salary else None,
        required_skills=required,
        preferred_skills=preferred,
        education=stats["education"],
        experience=stats["experience"],
        latest_posting=stats["latest_posting"],
        sources=SOURCES,
        limitations=LIMITATIONS,
    )
