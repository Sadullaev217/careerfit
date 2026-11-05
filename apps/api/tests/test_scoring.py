"""Known profiles with expected score ranges, plus the rules that make the score traceable."""

import json
from copy import deepcopy
from datetime import date
from typing import Any

import pytest

from app.profile_schema import ExtractedProfile
from app.scoring import (
    DISCLAIMER,
    EXPERIENCE_BAND_YEARS,
    WEIGHTS_PATH,
    JudgedSkill,
    MarketSnapshot,
    NothingToScore,
    ScoreInput,
    ScoreResult,
    credentials,
    education_rank,
    relevant_years,
    score_profile,
    target_years,
    weights_for,
)
from tests.helpers import VALID_PROFILE

AS_OF = date(2026, 11, 4)
SALARY = {
    "p25": 70_000,
    "median": 85_000,
    "p75": 100_000,
    "currency": "CAD",
    "period": "yearly",
    "sample_size": 200,
    "region": "Ontario",
    "confidence": "high",
    "concentrated": False,
}
MARKET = MarketSnapshot(
    occupation_code="21232",
    occupation_name="Software developers and programmers",
    region="Ontario",
    sample_size=334,
    education={"Bachelor's degree": 80, "College/CEGEP": 20},
    experience={"3 years to less than 5 years": 60, "1 year to less than 2 years": 40},
    salary=SALARY,
    latest_posting="2026-10-30",
)


def judged(levels: str, evidence: str = "Skill: Python") -> list[JudgedSkill]:
    names = {"y": "yes", "p": "partly", "n": "no"}
    return [
        JudgedSkill(
            name=f"skill {index}",
            level=names[code],  # type: ignore[arg-type]
            evidence=[] if code == "n" else [evidence],
        )
        for index, code in enumerate(levels)
    ]


def profile(**changes: Any) -> ExtractedProfile:
    return ExtractedProfile.model_validate({**deepcopy(VALID_PROFILE), **changes})


def job(start: str | None, end: str | None = None, is_current: bool = False) -> dict[str, Any]:
    return {
        "title": "Developer",
        "title_en": "Developer",
        "employer": None,
        "start_date": start,
        "end_date": end,
        "is_current": is_current,
        "confidence": 1,
    }


def make_input(**changes: Any) -> ScoreInput:
    values: dict[str, Any] = {
        "profile": profile(),
        "market": MARKET,
        "required": judged("yyyyyyyyyyynnnn"),
        "preferred": judged("yyyyynnnnn"),
        "relevant_job_indexes": [0],
        "relevant_credential_indexes": [0],
        "portfolio_links": 1,
        "as_of": AS_OF,
    }
    return ScoreInput(**{**values, **changes})


def points(result: ScoreResult) -> dict[str, int]:
    return {category.key: category.points for category in result.categories}


# --- Known profiles ---


def test_strong_match_scores_high() -> None:
    result = score_profile(make_input())
    assert 85 <= result.score <= 100


def test_partial_match_scores_in_the_middle() -> None:
    data = make_input(
        profile=profile(work_history=[job("2024-01", "2025-06")], seniority="junior", projects=[]),
        required=judged("yyyyyppnnnnnnnn"),
        preferred=judged("ynnnnnnnnn"),
        portfolio_links=0,
    )
    assert 35 <= score_profile(data).score <= 65


def test_wrong_field_scores_low() -> None:
    data = make_input(
        profile=profile(
            education=[],
            certifications=[],
            projects=[],
            work_history=[job("2015-01", is_current=True)],
            seniority="senior",
        ),
        required=judged("nnnnnnnnnnnnnnn"),
        preferred=judged("nnnnnnnnnn"),
        relevant_job_indexes=[],
        portfolio_links=0,
    )
    result = score_profile(data)
    assert result.score == 0
    assert "didn't find work in this occupation" in next(
        c.reason for c in result.categories if c.key == "seniority"
    )


def test_a_degree_alone_does_not_make_a_match() -> None:
    data = make_input(
        required=judged("nnnnnnnnnnnnnnn"),
        preferred=judged("nnnnnnnnnn"),
        relevant_job_indexes=[],
        relevant_credential_indexes=[],
        portfolio_links=0,
    )
    assert score_profile(data).score <= 5


def test_seniority_in_another_field_earns_nothing() -> None:
    data = make_input(profile=profile(seniority="lead"), relevant_job_indexes=[])
    assert points(score_profile(data))["seniority"] == 0


# --- Same input, same score ---


def test_same_input_gives_identical_output() -> None:
    first = score_profile(make_input()).model_dump_json()
    assert all(score_profile(make_input()).model_dump_json() == first for _ in range(20))


def test_score_doesnt_depend_on_the_order_of_jobs_listed() -> None:
    jobs = [job("2018-01", "2019-12"), job("2020-01", "2021-12")]
    forward = make_input(profile=profile(work_history=jobs), relevant_job_indexes=[0, 1])
    backward = make_input(profile=profile(work_history=jobs[::-1]), relevant_job_indexes=[1, 0])
    assert score_profile(forward).score == score_profile(backward).score


# --- Every point has a reason ---


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"required": judged("ypn")},
        {"required": []},
        {"preferred": []},
        {"relevant_job_indexes": []},
        {"profile": profile(seniority="unknown")},
        {"market": MarketSnapshot("31301", "Registered nurses", "Ontario", 12)},
        {"market": MarketSnapshot("99999", "Unknown", "Ontario", 500, experience={"No experience": 3})},
    ],
)
def test_points_add_up_to_the_score_and_each_has_a_reason(changes: dict[str, Any]) -> None:
    result = score_profile(make_input(**changes))
    assert sum(points(result).values()) == result.score
    assert sum(category.max_points for category in result.categories) == 100
    for category in result.categories:
        assert 0 <= category.points <= category.max_points
        assert category.reason


def test_fractions_never_lose_or_add_a_point() -> None:
    for yes_count in range(16):
        result = score_profile(make_input(required=judged("y" * yes_count + "n" * (15 - yes_count))))
        assert sum(points(result).values()) == result.score
        assert all(c.points <= c.max_points for c in result.categories)


def test_every_credited_skill_lists_its_evidence() -> None:
    result = score_profile(make_input(required=judged("yp")))
    assert all(skill.evidence for skill in result.required_skills)


def test_more_skills_never_lowers_the_score() -> None:
    scores = [
        score_profile(make_input(required=judged("y" * count + "n" * (15 - count)))).score
        for count in range(16)
    ]
    assert scores == sorted(scores)


def test_full_marks_for_skills_at_the_stated_coverage() -> None:
    result = score_profile(make_input(required=judged("yyyn")))
    required = next(c for c in result.categories if c.key == "required_skills")
    assert required.points == required.max_points
    assert "75%" in required.reason


def test_partly_counts_for_half() -> None:
    half = score_profile(make_input(required=judged("pppp")))
    full = score_profile(make_input(required=judged("yynn")))
    assert points(half)["required_skills"] == points(full)["required_skills"]


# --- Missing data doesn't count against anyone ---


def test_missing_skill_list_is_excluded_and_explained() -> None:
    result = score_profile(make_input(required=[]))
    assert "required_skills" not in points(result)
    assert any("Required skills" in note for note in result.not_scored)
    assert sum(category.max_points for category in result.categories) == 100


def test_full_credit_is_still_possible_when_data_is_missing() -> None:
    market = MarketSnapshot("21232", "Software developers", "Ontario", 334)
    result = score_profile(
        make_input(market=market, required=judged("yyyy"), preferred=judged("yy"), portfolio_links=3)
    )
    assert result.score == 100


def test_nothing_at_all_to_score_is_an_error_not_a_zero() -> None:
    market = MarketSnapshot("31301", "Registered nurses", "Ontario", 0)
    with pytest.raises(NothingToScore):
        score_profile(make_input(market=market, required=[], preferred=[]))


# --- Weights by industry ---


def test_every_weight_set_totals_100_and_names_every_category() -> None:
    config = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    expected = set(config["default"]["weights"])
    assert len(expected) == 6
    for entry in config.values():
        assert entry["name"]
        assert set(entry["weights"]) == expected
        assert sum(entry["weights"].values()) == 100


def test_weights_depend_on_the_field() -> None:
    assert weights_for("21232")["name"] == "Natural and applied sciences"
    assert weights_for("72106")["weights"]["portfolio"] == 0
    assert weights_for("51120")["weights"]["portfolio"] == 30
    assert weights_for("11100")["name"] == "General"


def test_the_same_person_scores_differently_by_field() -> None:
    tech = score_profile(make_input(portfolio_links=0, profile=profile(projects=[])))
    health_market = MarketSnapshot(
        "31301",
        "Registered nurses",
        "Ontario",
        334,
        education=MARKET.education,
        experience=MARKET.experience,
    )
    health = score_profile(
        make_input(market=health_market, portfolio_links=0, profile=profile(projects=[]))
    )
    assert "portfolio" in points(tech)
    assert "portfolio" not in points(health)
    assert any("Portfolio" in note for note in health.not_scored)
    assert health.weights_used == "Health"


# --- Experience ---


def test_overlapping_jobs_count_once() -> None:
    jobs = [job("2020-01", "2022-12"), job("2021-01", "2021-12")]
    years, unusable = relevant_years(profile(work_history=jobs), [0, 1], AS_OF)
    assert (years, unusable) == (3.0, 0)


def test_gaps_between_jobs_are_not_counted() -> None:
    jobs = [job("2018-01", "2018-12"), job("2021-01", "2021-12")]
    assert relevant_years(profile(work_history=jobs), [0, 1], AS_OF)[0] == 2.0


def test_the_reason_names_the_jobs_counted() -> None:
    jobs = [job("2018-01", "2019-12"), job("2020-01", "2021-12")]
    jobs[1]["title_en"] = "Backend Engineer"
    data = make_input(profile=profile(work_history=jobs), relevant_job_indexes=[1])
    reason = next(c.reason for c in score_profile(data).categories if c.key == "experience")
    assert "counting: Backend Engineer." in reason
    assert "Developer" not in reason


def test_one_year_reads_properly() -> None:
    market = MarketSnapshot("31301", "Nurses", "Ontario", 300, experience={"1 year to less than 2 years": 5})
    data = make_input(market=market, profile=profile(work_history=[job("2025-11", "2026-10")]))
    reason = next(c.reason for c in score_profile(data).categories if c.key == "experience")
    assert "You have 1 year of relevant experience" in reason
    assert "about 1 year." in reason


def test_the_reason_says_when_no_job_counted() -> None:
    reason = next(
        c.reason
        for c in score_profile(make_input(relevant_job_indexes=[])).categories
        if c.key == "experience"
    )
    assert "didn't find jobs in this occupation" in reason


def test_only_relevant_jobs_count() -> None:
    jobs = [job("2010-01", "2019-12"), job("2021-01", "2021-12")]
    assert relevant_years(profile(work_history=jobs), [1], AS_OF)[0] == 1.0


def test_current_job_runs_to_the_analysis_date() -> None:
    years, _ = relevant_years(profile(work_history=[job("2025-11", is_current=True)]), [0], AS_OF)
    assert years == 1.1


def test_year_only_dates_cover_the_whole_year() -> None:
    assert relevant_years(profile(work_history=[job("2019", "2020")]), [0], AS_OF)[0] == 2.0


def test_future_dates_are_cut_at_the_analysis_date() -> None:
    assert relevant_years(profile(work_history=[job("2030-01", "2031-01")]), [0], AS_OF)[0] == 0
    assert relevant_years(profile(work_history=[job("2026-01", "2031-01")]), [0], AS_OF)[0] == 0.9


def test_jobs_without_dates_are_reported_not_guessed() -> None:
    data = make_input(profile=profile(work_history=[job(None)]), relevant_job_indexes=[0])
    result = score_profile(data)
    assert points(result)["experience"] == 0
    assert "no usable dates" in next(c.reason for c in result.categories if c.key == "experience")


def test_a_bad_job_number_is_ignored() -> None:
    assert relevant_years(profile(), [7, -1], AS_OF) == (0, 0)


def test_typical_experience_uses_the_middle_ad() -> None:
    assert target_years({"No experience": 1, "5 years or more": 3}) == 5
    assert target_years({"No experience": 3, "5 years or more": 1}) == 0
    assert target_years({}) is None


def test_ads_not_requiring_experience_give_full_credit() -> None:
    market = MarketSnapshot("73300", "Truck drivers", "Ontario", 500, experience={"No experience": 9})
    result = score_profile(make_input(market=market, relevant_job_indexes=[]))
    assert points(result)["experience"] == max(c.max_points for c in result.categories if c.key == "experience")


@pytest.mark.parametrize("band", list(EXPERIENCE_BAND_YEARS))
def test_every_job_bank_band_is_understood(band: str) -> None:
    assert target_years({band.capitalize(): 1}) == EXPERIENCE_BAND_YEARS[band]


# --- Education ---


@pytest.mark.parametrize(
    ("label", "rank"),
    [
        # Every label seen in Job Bank data.
        ("No degree, certificate or diploma", 0),
        ("Secondary (high) school graduation certificate", 1),
        ("Other trades certificate or diploma", 2),
        ("Registered Apprenticeship certificate", 2),
        ("College/CEGEP", 3),
        ("College, CEGEP or other non-university certificate or diploma from a program of 1 year to 2 years", 3),
        ("Bachelor's degree", 4),
        ("Master's degree", 5),
        ("Earned doctorate degree", 6),
        ("Degree in medicine, dentistry, veterinary medicine or optometry", 6),
        # As written on resumes.
        ("BSc Computer Science", 4),
        ("BA Communications", 4),
        ("Bachelor of Science in Nursing", 4),
        ("B.Eng.", 4),
        ("Juris Doctor", 4),
        ("Postgraduate Certificate in Education (PGCE)", 4),
        ("MBA", 5),
        ("PhD", 6),
        ("Diploma in Culinary Arts", 3),
        ("бакалавр экономики", 4),
        ("магистр прикладной математики", 5),
        ("среднее специальное", 3),
        ("среднее образование", 1),
        ("Welding Certificate", 2),
        (None, None),
        ("", None),
        ("Some online courses", None),
    ],
)
def test_education_ranks(label: str | None, rank: int | None) -> None:
    assert education_rank(label) == rank


def _education_points(
    degree: str | None, in_field: bool = True, wanted: str = "Bachelor's degree"
) -> int:
    education = [
        {"degree": degree, "field_of_study": None, "institution": None, "end_year": None, "confidence": 1}
    ]
    changes = {"education": education, "certifications": []}
    market = MarketSnapshot("21232", "Developers", "Ontario", 334, education={wanted: 5})
    data = make_input(
        profile=profile(**changes), market=market, relevant_credential_indexes=[0] if in_field else []
    )
    return points(score_profile(data))["education"]


def test_meeting_or_beating_the_typical_education_earns_full_marks() -> None:
    full = _education_points("BSc Computer Science")
    assert full > 0
    assert _education_points("Master of Science") == full
    assert 0 < _education_points("College diploma") < full
    assert _education_points("Secondary school") == 0
    assert _education_points(None) == 0


def test_a_degree_in_another_field_earns_little() -> None:
    full = _education_points("BSc Computer Science")
    other_field = _education_points("BSc Computer Science", in_field=False)
    assert 0 < other_field < full / 2
    assert _education_points("Master of Science", in_field=False) == other_field


def test_the_reason_says_when_a_degree_is_in_another_field() -> None:
    data = make_input(relevant_credential_indexes=[])
    reason = next(c.reason for c in score_profile(data).categories if c.key == "education")
    assert "not clearly in this field" in reason


def test_a_lower_level_in_another_field_earns_nothing() -> None:
    assert _education_points("College diploma", in_field=False) == 0


def test_field_doesnt_matter_for_basic_schooling() -> None:
    wanted = "Secondary (high) school graduation certificate"
    full = _education_points("BSc Computer Science", wanted=wanted)
    assert _education_points("BSc Computer Science", in_field=False, wanted=wanted) == full
    assert _education_points("Secondary school", in_field=False, wanted=wanted) == full


def test_the_best_credential_counts_whatever_the_order() -> None:
    degrees = [
        {"degree": d, "field_of_study": None, "institution": None, "end_year": None, "confidence": 1}
        for d in ("BA History", "BSc Nursing")
    ]
    market = MarketSnapshot("31301", "Nurses", "Ontario", 334, education={"Bachelor's degree": 5})
    one = make_input(
        profile=profile(education=degrees), market=market, relevant_credential_indexes=[1]
    )
    two = make_input(
        profile=profile(education=degrees[::-1]), market=market, relevant_credential_indexes=[0]
    )
    for data in (one, two):
        education = next(c for c in score_profile(data).categories if c.key == "education")
        assert education.points == education.max_points


def test_degrees_with_no_recognisable_level_arent_listed() -> None:
    empty = {"degree": None, "field_of_study": None, "institution": "X", "end_year": None, "confidence": 1}
    vague = {**empty, "degree": "Some online courses"}
    real = {**empty, "degree": "BSc Physics", "field_of_study": "Physics"}
    held = credentials(profile(education=[empty, vague, real], certifications=[]))
    assert held == [("BSc Physics Physics", 4)]


def test_a_field_of_study_cant_pass_for_a_degree() -> None:
    education = [
        {
            "degree": None,
            "field_of_study": "College Administration",
            "institution": "Master's Academy",
            "end_year": None,
            "confidence": 1,
        }
    ]
    data = make_input(profile=profile(education=education, certifications=[]))
    assert points(score_profile(data))["education"] == 0


def test_a_certification_counts_as_a_credential() -> None:
    cert = [{"name": "Red Seal Welder", "issuer": None, "year": None, "confidence": 1}]
    market = MarketSnapshot("72106", "Welders", "Ontario", 300, education={"Other trades certificate or diploma": 5})
    data = make_input(market=market, profile=profile(education=[], certifications=cert))
    assert points(score_profile(data))["education"] > 0


def test_an_unrelated_certification_barely_counts() -> None:
    cert = [{"name": "Google Analytics", "issuer": None, "year": None, "confidence": 1}]
    market = MarketSnapshot("72106", "Welders", "Ontario", 300, education={"Other trades certificate or diploma": 5})
    data = make_input(
        market=market,
        profile=profile(education=[], certifications=cert),
        relevant_credential_indexes=[],
    )
    education = next(c for c in score_profile(data).categories if c.key == "education")
    assert 0 < education.points < education.max_points / 2


# --- Portfolio ---


def test_only_projects_backing_a_skill_count() -> None:
    unrelated = score_profile(make_input(portfolio_links=0))
    backing = score_profile(
        make_input(required=judged("yyyyyyyyyyynnnn", "Project: Ledger (Python)"), portfolio_links=0)
    )
    assert points(unrelated)["portfolio"] == 0
    assert points(backing)["portfolio"] > 0


def test_the_same_project_counted_once_however_often_cited() -> None:
    result = score_profile(make_input(required=judged("yyy", "Project: Ledger"), portfolio_links=0))
    assert "1 project(s)" in next(c.reason for c in result.categories if c.key == "portfolio")


def test_portfolio_links_count() -> None:
    assert points(score_profile(make_input(portfolio_links=3)))["portfolio"] == 15


# --- Salary ---


def test_salary_stays_within_the_market_middle() -> None:
    for required in ("nnnn", "ynnn", "yynn", "yyyy"):
        salary = score_profile(make_input(required=judged(required))).salary
        assert salary is not None
        assert 70_000 <= salary.low <= salary.high <= 100_000
        assert salary.market_median == 85_000


def test_stronger_profiles_get_higher_pay() -> None:
    weak = score_profile(make_input(required=judged("nnnn"), relevant_job_indexes=[])).salary
    strong = score_profile(make_input(required=judged("yyyy"))).salary
    assert weak is not None and strong is not None
    assert weak.low == 70_000
    assert strong.high == 100_000
    assert weak.low < strong.low and weak.high < strong.high


def test_a_low_match_says_the_pay_is_for_after_qualifying() -> None:
    low = make_input(
        required=judged("nnnnnnnnnnnnnnn"),
        preferred=judged("nnnnnnnnnn"),
        relevant_job_indexes=[],
        relevant_credential_indexes=[],
        portfolio_links=0,
    )
    salary = score_profile(low).salary
    assert salary is not None
    assert "once you qualify" in salary.basis
    strong = score_profile(make_input()).salary
    assert strong is not None
    assert "once you qualify" not in strong.basis


def test_salary_explains_its_source() -> None:
    salary = score_profile(make_input()).salary
    assert salary is not None
    assert "200 job ads in Ontario" in salary.basis


def test_no_pay_data_gives_no_salary() -> None:
    market = MarketSnapshot("21232", "Developers", "Ontario", 5, experience=MARKET.experience)
    assert score_profile(make_input(market=market)).salary is None


def test_one_pay_scale_is_flagged_on_the_salary_and_confidence() -> None:
    same = {**SALARY, "p25": 85_588, "median": 85_588, "p75": 85_588, "concentrated": True}
    market = MarketSnapshot("41220", "Teachers", "Ontario", 193, experience=MARKET.experience, salary=same)
    result = score_profile(make_input(market=market))
    assert result.salary is not None
    assert result.salary.concentrated
    assert result.salary.low == result.salary.high == 85_588
    assert result.confidence.level == "medium"


# --- Confidence ---


@pytest.mark.parametrize(
    ("sample_size", "level"), [(500, "high"), (100, "high"), (99, "medium"), (30, "medium"), (29, "low"), (0, "low")]
)
def test_confidence_drops_with_small_samples(sample_size: int, level: str) -> None:
    market = MarketSnapshot("21232", "Developers", "Ontario", sample_size, experience=MARKET.experience)
    result = score_profile(make_input(market=market))
    assert result.confidence.level == level
    assert result.confidence.reasons


def test_zero_ads_reads_properly() -> None:
    market = MarketSnapshot("21232", "Developers", "Nunavut", 0, experience=MARKET.experience)
    assert "No job ads" in score_profile(make_input(market=market)).confidence.reasons[0]


def test_using_national_requirements_is_stated_and_lowers_confidence() -> None:
    market = MarketSnapshot(
        "21232", "Developers", "Yukon", 334, experience=MARKET.experience, used_national_requirements=True
    )
    confidence = score_profile(make_input(market=market)).confidence
    assert confidence.level == "medium"
    assert any("all of Canada" in reason for reason in confidence.reasons)


def test_confidence_drops_without_a_real_skill_list() -> None:
    assert score_profile(make_input(required=judged("yy"))).confidence.level == "low"


def test_confidence_drops_for_suspicious_or_cut_off_resumes() -> None:
    assert score_profile(make_input(suspicious_content=True)).confidence.level == "low"
    assert score_profile(make_input(truncated=True)).confidence.level == "medium"


def test_confidence_drops_when_the_resume_says_little() -> None:
    bare = profile(skills=[], work_history=[], education=[], certifications=[], projects=[])
    result = score_profile(make_input(profile=bare, relevant_job_indexes=[]))
    assert result.confidence.level == "low"
    assert any("little to go on" in reason for reason in result.confidence.reasons)


def test_lower_reason_cant_raise_confidence_back_up() -> None:
    market = MarketSnapshot("21232", "Developers", "Ontario", 5, experience=MARKET.experience)
    result = score_profile(make_input(market=market, truncated=True))
    assert result.confidence.level == "low"
    assert len(result.confidence.reasons) == 2


def test_result_carries_the_disclaimer_and_its_inputs() -> None:
    result = score_profile(make_input())
    assert result.disclaimer == DISCLAIMER
    assert result.as_of == "2026-11-04"
    assert result.market_latest_posting == "2026-10-30"
    assert result.weights_used == "Natural and applied sciences"
