import json
from pathlib import Path
from typing import Any

from app.profile_schema import ExtractedProfile
from eval.run_mapping_eval import score_mapping
from eval.scoring import score_profile
from tests.helpers import VALID_PROFILE

RESUMES = json.loads(
    (Path(__file__).parents[1] / "eval" / "resumes.json").read_text(encoding="utf-8")
)

EXPECTED: dict[str, Any] = {
    "skills": [["python"], ["sql"]],
    "titles": [["developer"]],
    "employers": [["acme"]],
    "institutions": ["riverton"],
    "certifications": ["aws", "amazon"],
    "languages": ["english"],
    "projects": ["ledger"],
    "seniority": ["mid"],
    "must_flag": False,
    "forbidden": ["married"],
}


def profile(**overrides: Any) -> ExtractedProfile:
    return ExtractedProfile.model_validate({**VALID_PROFILE, **overrides})


def test_mapping_score_counts_each_outcome() -> None:
    items = [
        {"name": "Python", "accept": ["python"]},
        {"name": "Python", "accept": ["python"]},
        {"name": "Python", "accept": ["python"]},
        {"name": "React", "accept": []},
        {"name": "React", "accept": []},
    ]
    labels = ["Python (programming)", "pin parquet", None, None, "regulate chemical reaction"]
    assert score_mapping(items, labels) == {
        "correct": 1,
        "wrong": 2,
        "unmapped": 1,
        "correctly_unmapped": 1,
    }


def test_eval_set_meets_the_brief() -> None:
    assert len(RESUMES) >= 10
    assert len({resume["industry"] for resume in RESUMES}) >= 10
    assert {resume["language"] for resume in RESUMES} == {"en", "ru"}


def test_every_resume_has_a_complete_answer_key() -> None:
    for resume in RESUMES:
        assert set(resume["expected"]) == set(EXPECTED), resume["id"]
        assert resume["expected"]["skills"], resume["id"]


def test_eval_set_covers_the_risky_cases() -> None:
    assert any(r["expected"]["must_flag"] for r in RESUMES)
    assert any("quantum" in r["expected"]["forbidden"] for r in RESUMES)
    # The sanitizer can't match this rewording, so it still tests the model itself.
    assert any("blockchain" in r["expected"]["forbidden"] for r in RESUMES)
    assert sum(bool(r["expected"]["forbidden"]) for r in RESUMES) >= 3
    # Found in manual testing: a short resume with no skills section once returned no skills.
    assert any(r["id"] == "short-no-skills-section-en" for r in RESUMES)


def test_perfect_profile_scores_full_marks() -> None:
    scores = score_profile(profile(), EXPECTED)
    assert set(scores.values()) == {1.0}


def test_missing_skill_lowers_only_that_check() -> None:
    skills = [s for s in VALID_PROFILE["skills"] if s["name_en"] != "SQL"]
    scores = score_profile(profile(skills=skills), EXPECTED)
    assert scores["skills"] == 0.5
    assert scores["titles"] == 1.0


def test_forbidden_text_anywhere_fails_that_check() -> None:
    jobs = [{**VALID_PROFILE["work_history"][0], "employer": "Acme, married"}]
    assert score_profile(profile(work_history=jobs), EXPECTED)["no_forbidden_text"] == 0.0


def test_checks_with_nothing_expected_do_not_inflate_the_score() -> None:
    scores = score_profile(
        profile(), {**EXPECTED, "languages": [], "projects": [], "forbidden": []}
    )
    assert "languages" not in scores
    assert "projects" not in scores
    assert "no_forbidden_text" not in scores
    assert "flags" not in scores


def test_required_flag_is_checked() -> None:
    expected = {**EXPECTED, "must_flag": True}
    assert score_profile(profile(flags=[]), expected)["flags"] == 0.0
    flagged = [{"field": "education", "issue": "missing"}]
    assert score_profile(profile(flags=flagged), expected)["flags"] == 1.0


def test_wrong_seniority_fails_that_check() -> None:
    assert score_profile(profile(seniority="executive"), EXPECTED)["seniority"] == 0.0
