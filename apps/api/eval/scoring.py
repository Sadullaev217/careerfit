from typing import Any

from app.profile_schema import ExtractedProfile

CHECKS = (
    "skills",
    "titles",
    "employers",
    "institutions",
    "certifications",
    "languages",
    "projects",
    "seniority",
    "flags",
    "no_forbidden_text",
)


def _contains_any(haystacks: list[str], needles: list[str]) -> bool:
    lowered = [text.lower() for text in haystacks]
    return any(needle.lower() in text for needle in needles for text in lowered)


def _fraction_found(expected: list[str], found: list[str]) -> float | None:
    if not expected:
        return None
    return sum(_contains_any(found, [item]) for item in expected) / len(expected)


def _alias_fraction(expected: list[list[str]], found: list[str]) -> float | None:
    if not expected:
        return None
    return sum(_contains_any(found, aliases) for aliases in expected) / len(expected)


def score_profile(profile: ExtractedProfile, expected: dict[str, Any]) -> dict[str, float]:
    """Checks with nothing expected are left out, so they can't inflate the score."""
    skills = [skill.name_en for skill in profile.skills]
    titles = [job.title_en for job in profile.work_history]
    employers = [job.employer or "" for job in profile.work_history]
    # A resume may name only a type of school, which belongs in either field.
    institutions = [f"{item.institution or ''} {item.degree or ''}" for item in profile.education]
    certifications = [item.name for item in profile.certifications]
    languages = [item.name_en for item in profile.languages]
    projects = [item.name for item in profile.projects]

    results: dict[str, float | None] = {
        "skills": _alias_fraction(expected["skills"], skills),
        "titles": _alias_fraction(expected["titles"], titles),
        "employers": _alias_fraction(expected["employers"], employers),
        "institutions": _fraction_found_any(expected["institutions"], institutions),
        "certifications": _fraction_found_any(expected["certifications"], certifications),
        "languages": _fraction_found(expected["languages"], languages),
        "projects": _fraction_found_any(expected["projects"], projects),
        "seniority": float(profile.seniority in expected["seniority"]),
        "flags": float(bool(profile.flags)) if expected["must_flag"] else None,
        "no_forbidden_text": float(
            not _contains_any([profile.model_dump_json()], expected["forbidden"])
        )
        if expected["forbidden"]
        else None,
    }
    return {name: value for name, value in results.items() if value is not None}


def _fraction_found_any(aliases: list[str], found: list[str]) -> float | None:
    """The expected list holds alternative spellings of one thing."""
    if not aliases:
        return None
    return float(_contains_any(found, aliases))
