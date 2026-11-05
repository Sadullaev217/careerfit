"""The score formula. Plain arithmetic with no AI or randomness: the same input gives the same score.

There are deliberately no inputs for protected attributes, so they cannot affect the result.
"""

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.profile_schema import ExtractedProfile

Level = Literal["yes", "partly", "no"]
LEVEL_CREDIT: dict[str, float] = {"yes": 1.0, "partly": 0.5, "no": 0.0}

WEIGHTS_PATH = Path(__file__).resolve().parents[1] / "data" / "score_weights.json"
CATEGORY_LABELS = {
    "required_skills": "Required skills",
    "preferred_skills": "Other useful skills",
    "experience": "Relevant experience",
    "education": "Education",
    "portfolio": "Portfolio",
    "seniority": "Seniority",
}

# Few people show every skill in an official list. In testing, the right role averaged 52% coverage
# and the best reached 90%, so this much coverage earns full marks.
REQUIRED_COVERAGE_FOR_FULL_MARKS = 0.75
PREFERRED_COVERAGE_FOR_FULL_MARKS = 0.5
PORTFOLIO_ITEMS_FOR_FULL_MARKS = 3
BASIC_SCHOOLING_RANK = 1
OTHER_FIELD_CREDIT = 0.25

# The lower end of each band, as Job Bank words them.
EXPERIENCE_BAND_YEARS = {
    "no experience": 0.0,
    "1 to less than 7 months": 0.25,
    "7 months to less than 1 year": 0.6,
    "1 year to less than 2 years": 1.0,
    "2 years to less than 3 years": 2.0,
    "3 years to less than 5 years": 3.0,
    "5 years or more": 5.0,
}
SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "lead", "executive"]
SALARY_BAND_WIDTH = 0.2
MEDIUM_MARKET_SAMPLE = 100
LOW_MARKET_SAMPLE = 30
MIN_SKILLS_FOR_CONFIDENCE = 5
PROJECT_EVIDENCE_PREFIX = "Project: "
CERTIFICATION_PREFIX = "Certification: "
MIN_EVIDENCE_FOR_CONFIDENCE = 3
LOW_FIT_SCORE = 25
DISCLAIMER = (
    "This is an estimate to help you plan, not a guarantee of being hired or of any salary. It was "
    "made with AI, which can make mistakes."
)

# Checked in order, because labels overlap: "No degree, certificate or diploma" names a diploma.
_EDUCATION_LEVELS = (
    (r"no degree", 0),
    (r"juris|\bj\.?d\b|\bllb\b", 4),
    (r"doctor|\bph\.?d\b|кандидат|degree in medicine|\bm\.?d\b", 6),
    (r"master|\bm\.?sc?\b|\bm\.?a\b|\bmba\b|магистр", 5),
    (
        r"postgraduate|\bpgce\b|bachelor|\bb\.?sc?\b|\bb\.?a\b|\bb\.?eng\b|\bb\.?ed\b|\bb\.?com\b"
        r"|\bbba\b|\bbsn\b|бакалавр|специалист|высшее",
        4,
    ),
    (r"apprentice|trades", 2),
    (r"college|cegep|diploma|associate|колледж|среднее специальное|техникум|диплом", 3),
    (r"secondary|high school|среднее|школ", 1),
    (r"certificate|училище", 2),
)
_EDUCATION_NAMES = {
    0: "no formal credential",
    1: "secondary school",
    2: "a certificate or trade qualification",
    3: "a college diploma",
    4: "a bachelor's degree",
    5: "a master's degree",
    6: "a doctorate or medical degree",
}


class NothingToScore(Exception):
    pass


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class JudgedSkill(CamelModel):
    name: str
    level: Level
    evidence: list[str]


class Category(CamelModel):
    key: str
    label: str
    max_points: int
    points: int
    reason: str


class ProfileSalary(CamelModel):
    low: int
    high: int
    market_median: int
    currency: str
    sample_size: int
    region: str
    concentrated: bool
    basis: str


class Confidence(CamelModel):
    level: Literal["low", "medium", "high"]
    reasons: list[str]


class ScoreResult(CamelModel):
    score: int
    categories: list[Category]
    not_scored: list[str]
    required_skills: list[JudgedSkill]
    preferred_skills: list[JudgedSkill]
    salary: ProfileSalary | None
    confidence: Confidence
    occupation_code: str
    occupation_name: str
    region: str
    weights_used: str
    as_of: str
    market_latest_posting: str | None
    disclaimer: str


@dataclass(frozen=True)
class MarketSnapshot:
    occupation_code: str
    occupation_name: str
    region: str
    sample_size: int
    education: dict[str, int] = field(default_factory=dict)
    experience: dict[str, int] = field(default_factory=dict)
    salary: dict[str, Any] | None = None
    latest_posting: str | None = None
    used_national_requirements: bool = False


@dataclass(frozen=True)
class ScoreInput:
    profile: ExtractedProfile
    market: MarketSnapshot
    required: list[JudgedSkill]
    preferred: list[JudgedSkill]
    relevant_job_indexes: list[int]
    relevant_credential_indexes: list[int]
    portfolio_links: int
    as_of: date
    suspicious_content: bool = False
    truncated: bool = False


@lru_cache(maxsize=1)
def load_weights(path: Path = WEIGHTS_PATH) -> dict[str, dict[str, Any]]:
    weights: dict[str, dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return weights


def weights_for(occupation_code: str) -> dict[str, Any]:
    """The first digit of a Canadian occupation code is its broad field."""
    weights = load_weights()
    return weights.get(occupation_code[:1], weights["default"])


def education_rank(text: str | None) -> int | None:
    lowered = (text or "").lower()
    for pattern, rank in _EDUCATION_LEVELS:
        if re.search(pattern, lowered):
            return rank
    return None


def _month_number(value: str | None, end_of_year: bool) -> int | None:
    match = re.match(r"^(\d{4})(?:-(\d{1,2}))?", (value or "").strip())
    if not match:
        return None
    month = int(match.group(2)) if match.group(2) else (12 if end_of_year else 1)
    if not 1 <= month <= 12:
        return None
    return int(match.group(1)) * 12 + month - 1


def relevant_years(profile: ExtractedProfile, indexes: list[int], as_of: date) -> tuple[float, int]:
    """Overlapping jobs count once. Returns years, and how many relevant jobs had unusable dates."""
    today = as_of.year * 12 + as_of.month - 1
    spans: list[tuple[int, int]] = []
    unusable = 0
    for index in sorted(set(indexes)):
        if not 0 <= index < len(profile.work_history):
            continue
        job = profile.work_history[index]
        start = _month_number(job.start_date, end_of_year=False)
        end = today if job.is_current else _month_number(job.end_date, end_of_year=True)
        if start is None or end is None:
            unusable += 1
            continue
        if start <= today:
            spans.append((start, min(end, today)))

    months = 0
    current_start: int | None = None
    current_end = 0
    for start, end in sorted(spans):
        if end < start:
            continue
        if current_start is None or start > current_end + 1:
            if current_start is not None:
                months += current_end - current_start + 1
            current_start, current_end = start, end
        else:
            current_end = max(current_end, end)
    if current_start is not None:
        months += current_end - current_start + 1
    return round(months / 12, 1), unusable


def _weighted_median(values: list[tuple[float, int]]) -> float | None:
    total = sum(count for _, count in values)
    running = 0
    for value, count in sorted(values):
        running += count
        if running * 2 >= total > 0:
            return value
    return None


def target_years(experience: dict[str, int]) -> float | None:
    return _weighted_median(
        [
            (EXPERIENCE_BAND_YEARS[band.lower()], count)
            for band, count in experience.items()
            if band.lower() in EXPERIENCE_BAND_YEARS
        ]
    )


def skill_coverage(skills: list[JudgedSkill]) -> float:
    return sum(LEVEL_CREDIT[skill.level] for skill in skills) / len(skills) if skills else 0.0


def _skill_category(
    skills: list[JudgedSkill], full_marks_at: float, what: str
) -> tuple[float | None, str]:
    if not skills:
        return None, f"We don't have a reliable list of {what} for this occupation."
    shown = sum(skill.level == "yes" for skill in skills)
    partly = sum(skill.level == "partly" for skill in skills)
    return min(skill_coverage(skills) / full_marks_at, 1.0), (
        f"Your resume shows {shown} and partly shows {partly} of the {len(skills)} {what} we checked. "
        f"Covering {full_marks_at:.0%} earns full marks."
    )


def _years(value: float) -> str:
    return f"{value:g} year" if value == 1 else f"{value:g} years"


def _experience_category(data: ScoreInput) -> tuple[float | None, str, float | None]:
    target = target_years(data.market.experience)
    if target is None:
        return None, "Job ads for this role rarely state the experience wanted.", None
    years, unusable = relevant_years(data.profile, data.relevant_job_indexes, data.as_of)
    titles = [
        data.profile.work_history[index].title_en
        for index in sorted(set(data.relevant_job_indexes))
        if 0 <= index < len(data.profile.work_history)
    ]
    found = (
        f"You have {_years(years)} of relevant experience, counting: {', '.join(titles)}."
        if titles
        else "We didn't find jobs in this occupation on your resume."
    )
    note = f" {unusable} of these had no usable dates, so they aren't counted." if unusable else ""
    if target == 0:
        return 1.0, f"Most ads for this role don't require experience. {found}{note}", target
    return (
        min(years / target, 1.0),
        f"{found}{note} Typical ads ask for about {_years(target)}.",
        target,
    )


def credentials(profile: ExtractedProfile) -> list[tuple[str, int]]:
    """Each degree and certification with its level. Numbered in this order for the AI to refer to."""
    degrees = [
        (" ".join(filter(None, [item.degree, item.field_of_study])), rank)
        for item in profile.education
        if (rank := education_rank(item.degree)) is not None
    ]
    return degrees + [(f"{CERTIFICATION_PREFIX}{item.name}", 2) for item in profile.certifications]


def _credential_credit(rank: int, in_field: bool, wanted: float) -> float:
    # A software degree doesn't qualify anyone as a lawyer, but any diploma meets a high school ask.
    if wanted <= BASIC_SCHOOLING_RANK:
        return 1.0 if rank >= wanted else 0.0
    if not in_field:
        return OTHER_FIELD_CREDIT if rank >= wanted else 0.0
    return 1.0 if rank >= wanted else 0.5 if wanted - rank == 1 else 0.0


def _education_category(data: ScoreInput) -> tuple[float | None, str]:
    wanted = _weighted_median(
        [
            (float(rank), count)
            for level, count in data.market.education.items()
            if (rank := education_rank(level)) is not None
        ]
    )
    if wanted is None:
        return None, "Job ads for this role rarely state the education wanted."
    wanted_name = _EDUCATION_NAMES[int(wanted)]
    relevant = set(data.relevant_credential_indexes)
    found = [
        (_credential_credit(rank, index in relevant, wanted), rank, index in relevant)
        for index, (_, rank) in enumerate(credentials(data.profile))
    ]
    if not found:
        return (
            1.0 if wanted == 0 else 0.0,
            f"Typical ads ask for {wanted_name}. We couldn't find a credential on your resume.",
        )
    credit, rank, in_field = max(found)
    name = _EDUCATION_NAMES[rank]
    if wanted > BASIC_SCHOOLING_RANK and rank >= wanted and not in_field:
        return credit, f"Typical ads ask for {wanted_name}. You have {name}, but not clearly in this field."
    if rank >= wanted:
        return credit, f"Typical ads ask for {wanted_name}, and you have {name}."
    return credit, f"Typical ads ask for {wanted_name}, and we found {name}."


def _portfolio_category(data: ScoreInput) -> tuple[float, str]:
    # Only projects backing a skill for this role count, so unrelated work earns nothing here.
    projects = {
        item
        for skill in [*data.required, *data.preferred]
        for item in skill.evidence
        if item.startswith(PROJECT_EVIDENCE_PREFIX)
    }
    items = len(projects) + data.portfolio_links
    return min(items / PORTFOLIO_ITEMS_FOR_FULL_MARKS, 1.0), (
        f"{len(projects)} project(s) on your resume support skills for this role, and you added "
        f"{data.portfolio_links} portfolio link(s). {PORTFOLIO_ITEMS_FOR_FULL_MARKS} items earn full marks."
    )


def _seniority_category(data: ScoreInput, target: float | None) -> tuple[float | None, str]:
    level = data.profile.seniority
    if level == "unknown" or target is None:
        return None, "We couldn't compare your level with this role."
    if not data.relevant_job_indexes:
        return 0.0, "We didn't find work in this occupation to compare your level with."
    expected = "senior" if target >= 5 else "mid" if target >= 1 else "junior"
    gap = SENIORITY_ORDER.index(expected) - SENIORITY_ORDER.index(level)
    credit = 1.0 if gap <= 0 else 0.6 if gap == 1 else 0.25 if gap == 2 else 0.0
    return credit, f"Your resume reads as {level}, and typical ads suit {expected} level."


def _whole_numbers(values: dict[str, float]) -> dict[str, int]:
    """Rounds each part so the parts still add up exactly to the rounded total."""
    rounded = {key: math.floor(value) for key, value in values.items()}
    leftover = round(sum(values.values())) - sum(rounded.values())
    for key in sorted(values, key=lambda k: (rounded[k] - values[k], k))[:leftover]:
        rounded[key] += 1
    return rounded


def _salary(
    data: ScoreInput, experience_credit: float | None, skills_credit: float | None, score: int
) -> ProfileSalary | None:
    market = data.market.salary
    if not market:
        return None
    known = [credit for credit in (experience_credit, skills_credit) if credit is not None]
    position = sum(known) / len(known) if known else 0.5
    spread = market["p75"] - market["p25"]
    centre = market["p25"] + spread * position
    caveat = " Your match is low, so this is what you could reach once you qualify." if score < LOW_FIT_SCORE else ""
    return ProfileSalary(
        low=round(max(centre - spread * SALARY_BAND_WIDTH, market["p25"])),
        high=round(min(centre + spread * SALARY_BAND_WIDTH, market["p75"])),
        market_median=round(market["median"]),
        currency=market["currency"],
        sample_size=market["sample_size"],
        region=market["region"],
        concentrated=market["concentrated"],
        basis=(
            f"Placed within the middle half of {market['sample_size']} job ads in {market['region']}, "
            f"based on your experience and skills.{caveat}"
        ),
    )


def _confidence(data: ScoreInput) -> Confidence:
    reasons: list[str] = []
    level: Literal["low", "medium", "high"] = "high"

    def lower_to(new: Literal["low", "medium"], reason: str) -> None:
        nonlocal level
        reasons.append(reason)
        if new == "low" or level == "high":
            level = new

    size = data.market.sample_size
    if size < LOW_MARKET_SAMPLE:
        count = f"Only {size}" if size else "No"
        lower_to("low", f"{count} job ads for this role and region.")
    elif size < MEDIUM_MARKET_SAMPLE:
        lower_to("medium", f"A moderate number of job ads for this role and region ({size}).")
    if data.market.used_national_requirements:
        lower_to("medium", "Few local ads state the education or experience wanted, so we used all of Canada.")
    if len(data.required) < MIN_SKILLS_FOR_CONFIDENCE:
        lower_to("low", "There is little official skill information for this occupation.")
    profile = data.profile
    evidence = len(profile.skills) + len(profile.work_history) + len(profile.projects) + len(credentials(profile))
    if evidence < MIN_EVIDENCE_FOR_CONFIDENCE:
        lower_to("low", "Your resume gave us little to go on, so treat this as a rough guide.")
    if data.market.salary and data.market.salary["concentrated"]:
        lower_to("medium", "Most ads list the same pay, often from one employer or pay scale.")
    if data.suspicious_content:
        lower_to("low", "Your resume contained text aimed at AI tools, which we removed.")
    if data.truncated:
        lower_to("medium", "Your resume was very long, so only the first part was read.")
    if not reasons:
        reasons.append("Plenty of job ads and a full skill list for this occupation.")
    return Confidence(level=level, reasons=reasons)


def score_profile(data: ScoreInput) -> ScoreResult:
    required_credit, required_reason = _skill_category(
        data.required, REQUIRED_COVERAGE_FOR_FULL_MARKS, "required skills"
    )
    preferred_credit, preferred_reason = _skill_category(
        data.preferred, PREFERRED_COVERAGE_FOR_FULL_MARKS, "other useful skills"
    )
    experience_credit, experience_reason, target = _experience_category(data)
    education_credit, education_reason = _education_category(data)
    portfolio_credit, portfolio_reason = _portfolio_category(data)
    seniority_credit, seniority_reason = _seniority_category(data, target)

    results: dict[str, tuple[float | None, str]] = {
        "required_skills": (required_credit, required_reason),
        "preferred_skills": (preferred_credit, preferred_reason),
        "experience": (experience_credit, experience_reason),
        "education": (education_credit, education_reason),
        "portfolio": (portfolio_credit, portfolio_reason),
        "seniority": (seniority_credit, seniority_reason),
    }
    config = weights_for(data.market.occupation_code)
    base: dict[str, int] = config["weights"]
    # Missing market data shouldn't count against anyone, so its share goes to the other categories.
    scored = {key: base[key] for key, (credit, _) in results.items() if credit is not None and base[key]}
    total_weight = sum(scored.values())
    if not total_weight:
        raise NothingToScore
    max_points = _whole_numbers({key: value * 100 / total_weight for key, value in scored.items()})
    points = _whole_numbers({key: (results[key][0] or 0.0) * max_points[key] for key in scored})

    not_scored: list[str] = []
    for key, (credit, reason) in results.items():
        if not base[key]:
            not_scored.append(f"{CATEGORY_LABELS[key]}: not usually weighed in this field.")
        elif credit is None:
            not_scored.append(f"{CATEGORY_LABELS[key]}: {reason}")

    score = sum(points.values())
    return ScoreResult(
        score=score,
        categories=[
            Category(
                key=key,
                label=CATEGORY_LABELS[key],
                max_points=max_points[key],
                points=points[key],
                reason=results[key][1],
            )
            for key in scored
        ],
        not_scored=not_scored,
        required_skills=data.required,
        preferred_skills=data.preferred,
        salary=_salary(data, experience_credit, required_credit, score),
        confidence=_confidence(data),
        occupation_code=data.market.occupation_code,
        occupation_name=data.market.occupation_name,
        region=data.market.region,
        weights_used=config["name"],
        as_of=data.as_of.isoformat(),
        market_latest_posting=data.market.latest_posting,
        disclaimer=DISCLAIMER,
    )
