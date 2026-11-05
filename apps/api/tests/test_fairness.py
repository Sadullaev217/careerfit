"""Changing protected attributes in the input must not change the score.

The fake AI here is deliberately prejudiced: it gives a poor result the moment it sees a protected detail.
So these tests fail if one ever reaches it, not only if the formula uses one.
"""

import json
import re
from copy import deepcopy
from dataclasses import fields
from datetime import date
from typing import Any

import pytest

from app.analysis import analyze
from app.extraction import extract_profile
from app.profile_schema import ExtractedProfile
from app.recommendations import suggest_rewrites
from app.scoring import ScoreInput, ScoreResult
from app.skill_judgement import relevance_message, skills_message
from tests.helpers import VALID_PROFILE

RESUME = """Work experience
Software Developer, 2019-01 to present
Built backend services in Python and SQL.

Education
BSc Computer Science, 2018

Skills
Python, SQL
"""
STATS: dict[str, Any] = {
    "sample_size": 334,
    "salary_sample_size": 150,
    "salary_p25": 70000,
    "salary_median": 85000,
    "salary_p75": 100000,
    "salary_top_share": 0.1,
    "latest_posting": "2026-10-30",
    "education": {"Bachelor's degree": 8},
    "experience": {"3 years to less than 5 years": 8},
}
SKILLS = [
    {"required": True, "rank": 1, "skills": {"name": "computer programming"}},
    {"required": True, "rank": 2, "skills": {"name": "debug software"}},
    {"required": False, "rank": 3, "skills": {"name": "agile"}},
]
PROTECTED_LINES = [
    "Date of birth: 12 March 1961",
    "DOB: 1998-02-14",
    "Age: 63",
    "Gender: Female",
    "Sex: Male",
    "Female.",
    "Nationality: Nigerian",
    "Citizenship: Pakistani",
    "Marital status: Married",
    "Married, three children.",
    "Religion: Muslim",
    "Дата рождения: 12.03.1961",
    "Возраст: 63",
    "Пол: женщина",
    "Гражданство: Узбекистан",
    "Национальность: таджик",
    "Семейное положение: замужем",
    "Вероисповедание: ислам",
]
PREJUDICE_TRIGGERS = re.compile(
    r"birth|dob\b|\bage\b|gender|\bsex\b|female|\bmale\b|nationality|nigerian|citizenship|pakistani"
    r"|marital|married|children|religion|muslim|рожден|возраст|\bпол\b|женщин|гражданство|узбекистан"
    r"|национальность|таджик|семейное|замужем|вероисповедание|ислам",
    re.IGNORECASE,
)


class PrejudicedLLM:
    model = "fake-model"

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.saw_protected_detail = False

    def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
        self.messages.append(user)
        prejudiced = bool(PREJUDICE_TRIGGERS.search(user))
        self.saw_protected_detail = self.saw_protected_detail or prejudiced
        properties = schema.get("properties", {})
        if "judgements" in properties:
            good = {"skill": 1, "level": "yes", "evidence": [1]}
            bad = {"skill": 1, "level": "no", "evidence": []}
            return json.dumps({"judgements": [bad if prejudiced else good]})
        if "rewrites" in properties:
            return json.dumps({"rewrites": []})
        if "jobs" in properties:
            fits = "no" if prejudiced else "yes"
            return json.dumps(
                {"jobs": [{"job": 1, "fits": fits}], "education": [{"item": 1, "fits": fits}]}
            )
        return json.dumps(
            {**deepcopy(VALID_PROFILE), "seniority": "intern" if prejudiced else "senior"}
        )


class Store:
    def __init__(self) -> None:
        self.saved: dict[tuple[str, str], dict[str, Any]] = {}

    def market_stats(self, _code: str, _region: str | None) -> dict[str, Any]:
        return STATS

    def occupation_skills(self, _code: str) -> list[dict[str, Any]]:
        return SKILLS

    def list_documents(self, _user_id: str) -> list[dict[str, Any]]:
        return []

    def get_skill_judgement(self, document_id: str, key: str) -> dict[str, Any] | None:
        return self.saved.get((document_id, key))

    def save_skill_judgement(self, document_id: str, key: str, result: dict[str, Any]) -> None:
        self.saved[(document_id, key)] = result


def embed(texts: list[str]) -> list[list[float]]:
    return [[float(i == n) for n in range(len(texts))] for i in range(len(texts))]


def full_pipeline(resume: str, llm: PrejudicedLLM) -> ScoreResult:
    extracted = extract_profile(resume, llm)
    return analyze(
        extraction={
            "data": extracted.profile.model_dump(),
            "suspicious_content": extracted.suspicious_content,
            "truncated": extracted.truncated,
        },
        document_id="doc",
        user_id="user",
        occupation_code="21232",
        occupation_name="Software developers",
        region="Ontario",
        as_of=date(2026, 11, 4),
        store=Store(),
        llm=llm,
        embed=embed,
    )


def score_with(profile: dict[str, Any]) -> ScoreResult:
    class Fixed(PrejudicedLLM):
        def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
            self.messages.append(user)
            if "judgements" in schema["properties"]:
                return json.dumps({"judgements": [{"skill": 1, "level": "yes", "evidence": [1]}]})
            return json.dumps(
                {"jobs": [{"job": 1, "fits": "yes"}], "education": [{"item": 1, "fits": "yes"}]}
            )

    return analyze(
        extraction={"data": profile},
        document_id="doc",
        user_id="user",
        occupation_code="21232",
        occupation_name="Software developers",
        region="Ontario",
        as_of=date(2026, 11, 4),
        store=Store(),
        llm=Fixed(),
        embed=embed,
    )


def test_the_prejudiced_ai_really_would_change_the_score() -> None:
    """Without this, the tests below could pass even if the fake never reacted to anything."""
    fair = PrejudicedLLM()
    unfair_llm = PrejudicedLLM()

    class Unfiltered(PrejudicedLLM):
        def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
            return unfair_llm.complete_json(system, user + "\nGender: Female", schema, attempt)

    assert full_pipeline(RESUME, fair).score != full_pipeline(RESUME, Unfiltered()).score
    assert not fair.saw_protected_detail
    assert unfair_llm.saw_protected_detail


@pytest.mark.parametrize("line", PROTECTED_LINES)
def test_a_protected_detail_never_reaches_the_ai(line: str) -> None:
    llm = PrejudicedLLM()
    full_pipeline(f"{line}\n\n{RESUME}", llm)
    assert not llm.saw_protected_detail


@pytest.mark.parametrize("line", PROTECTED_LINES)
def test_a_protected_detail_doesnt_change_the_result(line: str) -> None:
    baseline = full_pipeline(RESUME, PrejudicedLLM())
    assert full_pipeline(f"{line}\n{RESUME}", PrejudicedLLM()) == baseline
    assert full_pipeline(f"{RESUME}\n{line}", PrejudicedLLM()) == baseline


def test_all_protected_details_together_dont_change_the_result() -> None:
    baseline = full_pipeline(RESUME, PrejudicedLLM())
    details = "\n".join(PROTECTED_LINES)
    assert full_pipeline(f"{details}\n{RESUME}", PrejudicedLLM()) == baseline


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Gender: Female", "Gender: Male"),
        ("Date of birth: 1961-03-12", "Date of birth: 2002-03-12"),
        ("Nationality: Canadian", "Nationality: Nigerian"),
        ("Religion: Christian", "Religion: Muslim"),
        ("Marital status: Single", "Marital status: Married"),
        ("Пол: мужчина", "Пол: женщина"),
    ],
)
def test_swapping_a_protected_value_gives_the_same_ai_input_and_result(first: str, second: str) -> None:
    one, two = PrejudicedLLM(), PrejudicedLLM()
    assert full_pipeline(f"{first}\n{RESUME}", one) == full_pipeline(f"{second}\n{RESUME}", two)
    assert one.messages == two.messages


@pytest.mark.parametrize(
    "header",
    [
        "Emily Walsh",
        "Lakisha Washington, RN",
        "Mohammed Al-Farsi | Toronto",
        "Nguyen Thi Lan",
        "Абдуллаева Зарина",
        "Wei Zhang\nwei.zhang@example.com | +1 416 555 0100\nlinkedin.com/in/weizhang",
    ],
)
def test_a_different_name_gives_the_same_ai_input_and_result(header: str) -> None:
    named, baseline = PrejudicedLLM(), PrejudicedLLM()
    result = full_pipeline(f"{header}\n{RESUME}", named)
    assert result == full_pipeline(RESUME, baseline)
    assert named.messages == baseline.messages


def test_the_same_resume_twice_gives_the_same_ai_input() -> None:
    first, second = PrejudicedLLM(), PrejudicedLLM()
    full_pipeline(RESUME, first)
    full_pipeline(RESUME, second)
    assert first.messages == second.messages


@pytest.mark.parametrize("line", PROTECTED_LINES)
def test_a_protected_detail_never_reaches_the_rewrite_question(line: str) -> None:
    llm = PrejudicedLLM()
    work = "Built backend services in Python and SQL for several large clients."
    suggest_rewrites(f"Emily Walsh\n{line}\n{work}", llm)
    assert not llm.saw_protected_detail
    assert llm.messages == [f"LINES:\n1. {work}"]


def test_nothing_in_the_profile_can_hold_a_protected_attribute() -> None:
    schema = json.dumps(ExtractedProfile.model_json_schema()).lower()
    for word in (
        "gender", "birth", "\"age\"", "nationality", "citizenship", "religion", "marital",
        "ethnic", "race", "disability", "photo", "full_name", "first_name", "last_name",
    ):  # fmt: skip
        assert word not in schema


def test_the_formula_takes_no_protected_input() -> None:
    assert {f.name for f in fields(ScoreInput)} == {
        "profile",
        "market",
        "required",
        "preferred",
        "relevant_job_indexes",
        "relevant_credential_indexes",
        "portfolio_links",
        "as_of",
        "suspicious_content",
        "truncated",
    }


def _changed(**changes: dict[str, Any]) -> dict[str, Any]:
    profile = deepcopy(VALID_PROFILE)
    for section, values in changes.items():
        for row in profile[section]:
            row.update(values)
    return profile


@pytest.mark.parametrize(
    "changes",
    [
        {"work_history": {"employer": "Women in Tech Society"}},
        {"work_history": {"employer": "Islamic Relief"}},
        {"education": {"institution": "Howard University"}},
        {"education": {"institution": "Riverton Community College"}},
        {"education": {"end_year": 1975}},
        {"education": {"end_year": 2024}},
        {"certifications": {"issuer": "Muslim Professionals Network"}},
        {"certifications": {"year": 1980}},
        {"languages": {"name_en": "Arabic", "level": "native"}},
        {"languages": {"name_en": "Mandarin", "level": "native"}},
    ],
)
def test_details_hinting_at_background_dont_change_the_result(changes: dict[str, Any]) -> None:
    assert score_with(_changed(**changes)) == score_with(deepcopy(VALID_PROFILE))


def test_the_skill_prompt_leaves_out_employers_schools_languages_and_years() -> None:
    profile = ExtractedProfile.model_validate(
        _changed(
            work_history={"employer": "EMPLOYER-X"},
            education={"institution": "SCHOOL-X", "end_year": 1975},
            certifications={"issuer": "ISSUER-X", "year": 1980},
            languages={"name_en": "LANGUAGE-X"},
        )
    )
    message = skills_message(profile, "Developers", ["a"]) + relevance_message(profile, "Developers")
    for hidden in ("EMPLOYER-X", "SCHOOL-X", "ISSUER-X", "LANGUAGE-X", "1975", "1980"):
        assert hidden not in message


def test_extra_experience_beyond_the_typical_ask_gives_no_advantage() -> None:
    """Age shows up indirectly as long careers, so years stop counting once the ask is met."""
    enough = _changed(work_history={"start_date": "2022-01", "is_current": True})
    decades = _changed(work_history={"start_date": "1985-01", "is_current": True})
    assert score_with(enough).score == score_with(decades).score
