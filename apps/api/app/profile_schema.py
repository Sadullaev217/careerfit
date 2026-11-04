"""Output of resume extraction. There are deliberately no fields for protected attributes."""

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Field(ge=0, le=1)
SkillLevel = Literal["beginner", "intermediate", "advanced", "expert", "unknown"]
Seniority = Literal["intern", "junior", "mid", "senior", "lead", "executive", "unknown"]
FlaggedField = Literal[
    "work_history",
    "work_dates",
    "education",
    "skills",
    "certifications",
    "languages",
    "industry",
    "seniority",
    "projects",
]


class SkillItem(BaseModel):
    name: str
    name_en: str
    level: SkillLevel
    years: float | None
    confidence: float = Confidence


class JobItem(BaseModel):
    title: str
    title_en: str
    employer: str | None
    start_date: str | None
    end_date: str | None
    is_current: bool
    confidence: float = Confidence


class EducationItem(BaseModel):
    degree: str | None
    field_of_study: str | None
    institution: str | None
    end_year: int | None
    confidence: float = Confidence


class CertificationItem(BaseModel):
    name: str
    issuer: str | None
    year: int | None
    confidence: float = Confidence


class LanguageItem(BaseModel):
    name_en: str
    level: str | None
    confidence: float = Confidence


class ProjectItem(BaseModel):
    name: str
    demonstrates_en: list[str]
    confidence: float = Confidence


class InfoFlag(BaseModel):
    # Closed values rather than free text, so a flag can't repeat personal details.
    field: FlaggedField
    issue: Literal["missing", "ambiguous"]


class ExtractedProfile(BaseModel):
    skills: list[SkillItem]
    work_history: list[JobItem]
    education: list[EducationItem]
    certifications: list[CertificationItem]
    languages: list[LanguageItem]
    projects: list[ProjectItem]
    industry_en: str | None
    industry_confidence: float = Confidence
    seniority: Seniority
    seniority_confidence: float = Confidence
    flags: list[InfoFlag]
