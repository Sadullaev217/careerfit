import json
import os
from copy import deepcopy
from typing import Any

import pytest

from app.profile_schema import ExtractedProfile
from app.skill_judgement import (
    MIN_COVERAGE_TO_BACK_A_DEGREE,
    MIN_RELATED_SIMILARITY,
    SkillJudgementFailed,
    credentials_in_field,
    evidence_items,
    judge_skills,
    judgement_key,
    relevance_message,
    skills_message,
)
from tests.helpers import VALID_PROFILE

PROFILE = ExtractedProfile.model_validate(deepcopy(VALID_PROFILE))
# Evidence: 1 Skill: Python, 2 Skill: SQL, 3 Job title: Developer, 4 Project: Ledger, 5 Degree, 6 Certification.


class FakeLLM:
    model = "fake-model"

    def __init__(self, *skills: Any, relevance: Any = None) -> None:
        self.skills = list(skills)
        self.relevance = relevance if relevance is not None else fits()
        self.messages: list[str] = []

    def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
        self.messages.append(user)
        if "judgements" in schema["properties"]:
            answer = self.skills.pop(0)
        else:
            answer = self.relevance.pop(0) if isinstance(self.relevance, list) else self.relevance
        return answer if isinstance(answer, str) else json.dumps(answer)


def no_embedding(_texts: list[str]) -> list[list[float]]:
    raise AssertionError("similarity should not be needed here")


def unrelated(texts: list[str]) -> list[list[float]]:
    # Each text points its own way, so nothing is similar to anything else.
    return [[float(index == position) for position in range(len(texts))] for index in range(len(texts))]


def answer(*judgements: tuple[int, str, list[int]]) -> dict[str, Any]:
    return {"judgements": [{"skill": s, "level": level, "evidence": e} for s, level, e in judgements]}


def fits(jobs: list[int] | None = None, education: list[int] | None = None) -> dict[str, Any]:
    return {
        "jobs": [{"job": number, "fits": "yes"} for number in jobs or []],
        "education": [{"item": number, "fits": "yes"} for number in education or []],
    }


def test_evidence_is_built_from_skills_jobs_projects_and_certifications() -> None:
    assert evidence_items(PROFILE) == [
        "Skill: Python",
        "Skill: SQL",
        "Job title: Developer",
        "Project: Ledger (Python)",
        "Degree: BSc Computing",
        "Certification: AWS Developer",
    ]


def test_cited_evidence_is_shown_with_each_skill() -> None:
    llm = FakeLLM(answer((1, "yes", [1, 4]), (2, "partly", [2]), (3, "no", [])), relevance=fits(jobs=[1]))
    result = judge_skills(PROFILE, "Developers", ["programming", "databases", "welding"], [], llm, unrelated)
    assert [skill.level for skill in result.required] == ["yes", "partly", "no"]
    assert result.required[0].evidence == ["Skill: Python", "Project: Ledger (Python)"]
    assert result.required[2].evidence == []
    assert result.relevant_job_indexes == [0]


def test_required_and_other_skills_are_asked_together_and_split_back() -> None:
    llm = FakeLLM(answer((1, "yes", [1]), (2, "partly", [2])))
    result = judge_skills(PROFILE, "Developers", ["programming"], ["databases"], llm, unrelated)
    assert [skill.name for skill in result.required] == ["programming"]
    assert [skill.name for skill in result.preferred] == ["databases"]
    assert result.preferred[0].level == "partly"


def test_a_claim_without_evidence_is_rejected() -> None:
    llm = FakeLLM(answer((1, "yes", [])))
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert result.required[0].level == "no"


def test_made_up_evidence_numbers_are_rejected() -> None:
    llm = FakeLLM(answer((1, "yes", [99, 0, -3])))
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert result.required[0].level == "no"
    assert result.required[0].evidence == []


def test_real_evidence_survives_alongside_made_up_numbers() -> None:
    llm = FakeLLM(answer((1, "yes", [99, 1])))
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert result.required[0].evidence == ["Skill: Python"]


def test_skills_the_model_skipped_count_as_not_shown() -> None:
    llm = FakeLLM(answer((1, "yes", [1])))
    result = judge_skills(PROFILE, "Developers", ["programming", "databases"], [], llm, unrelated)
    assert [skill.level for skill in result.required] == ["yes", "no"]


def test_answers_about_skills_not_asked_are_ignored() -> None:
    llm = FakeLLM(answer((1, "no", []), (9, "yes", [1])))
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert len(result.required) == 1
    assert result.required[0].level == "no"


def test_the_first_answer_for_a_skill_wins() -> None:
    llm = FakeLLM(answer((1, "no", []), (1, "yes", [1])))
    assert judge_skills(PROFILE, "Developers", ["a"], [], llm, unrelated).required[0].level == "no"


def test_invalid_output_is_retried_once() -> None:
    llm = FakeLLM("not json", answer((1, "yes", [1])))
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert result.required[0].level == "yes"
    assert len(llm.messages) == 3  # two tries at the skills, then the relevance question


def test_repeatedly_invalid_output_fails_rather_than_guessing() -> None:
    llm = FakeLLM("not json", {"judgements": "nope"})
    with pytest.raises(SkillJudgementFailed):
        judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)


def test_invalid_relevance_output_also_fails() -> None:
    llm = FakeLLM(answer((1, "yes", [1])), relevance=["not json", {"jobs": "nope"}])
    with pytest.raises(SkillJudgementFailed):
        judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)


def test_invalid_relevance_output_is_retried() -> None:
    llm = FakeLLM(answer((1, "yes", [1])), relevance=["not json", fits(jobs=[1])])
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert result.relevant_job_indexes == [0]


def test_no_skill_list_still_asks_which_jobs_are_relevant() -> None:
    llm = FakeLLM(relevance=fits(jobs=[1]))
    result = judge_skills(PROFILE, "Developers", [], [], llm, no_embedding)
    assert result.required == []
    assert result.relevant_job_indexes == [0]
    assert len(llm.messages) == 1


def test_nothing_to_ask_skips_the_model() -> None:
    bare = PROFILE.model_copy(update={"work_history": [], "education": [], "certifications": []})
    llm = FakeLLM()
    result = judge_skills(bare, "Developers", [], [], llm, no_embedding)
    assert (result.required, result.relevant_job_indexes, result.relevant_credential_indexes) == ([], [], [])
    assert llm.messages == []


def test_prompts_name_the_occupation_being_compared() -> None:
    assert "OCCUPATION: Welders" in skills_message(PROFILE, "Welders", ["a"])
    assert "OCCUPATION: Welders" in relevance_message(PROFILE, "Welders")


# --- Relevant jobs and education ---


def test_only_jobs_answered_yes_count() -> None:
    relevance = {"jobs": [{"job": 1, "fits": "no"}], "education": []}
    llm = FakeLLM(answer((1, "no", [])), relevance=relevance)
    assert judge_skills(PROFILE, "Welders", ["a"], [], llm, unrelated).relevant_job_indexes == []


def test_invalid_job_and_education_numbers_are_ignored() -> None:
    llm = FakeLLM(answer((1, "yes", [1])), relevance=fits(jobs=[1, 2, 0, 99], education=[1, 3, 0, 99]))
    result = judge_skills(PROFILE, "Developers", ["a"], [], llm, unrelated)
    assert result.relevant_job_indexes == [0]
    assert result.relevant_credential_indexes == [0]


def test_education_lists_degrees_then_certifications() -> None:
    assert "EDUCATION:\n1. BSc Computing\n2. Certification: AWS Developer" in relevance_message(PROFILE, "X")


def test_a_degree_backed_by_a_relevant_job_counts() -> None:
    llm = FakeLLM(answer((1, "no", [])), relevance=fits(jobs=[1], education=[1]))
    assert judge_skills(PROFILE, "Developers", ["a"], [], llm, unrelated).relevant_credential_indexes == [0]


def test_a_degree_backed_by_skills_counts() -> None:
    llm = FakeLLM(answer((1, "yes", [1])), relevance=fits(education=[1]))
    assert judge_skills(PROFILE, "Developers", ["a"], [], llm, unrelated).relevant_credential_indexes == [0]


def test_a_degree_with_nothing_behind_it_doesnt_count() -> None:
    llm = FakeLLM(answer((1, "no", [])), relevance=fits(education=[1]))
    assert judge_skills(PROFILE, "Lawyers", ["a"], [], llm, unrelated).relevant_credential_indexes == []


def test_a_new_graduates_degree_named_after_the_job_counts() -> None:
    def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    assert credentials_in_field([0], ["Bachelor of Nursing"], "Nurses", False, 0.0, embed) == [0]


def test_coverage_just_below_the_line_doesnt_back_a_degree() -> None:
    below = MIN_COVERAGE_TO_BACK_A_DEGREE - 0.01
    assert credentials_in_field([0], ["BSc"], "Lawyers", False, below, unrelated) == []
    assert credentials_in_field([0], ["BSc"], "Lawyers", False, MIN_COVERAGE_TO_BACK_A_DEGREE, no_embedding) == [0]


def test_a_degree_the_ai_rejected_is_never_rescued() -> None:
    assert credentials_in_field([], ["BSc"], "Developers", True, 1.0, no_embedding) == []


# --- Job titles as evidence ---


def test_a_job_title_counts_as_evidence_for_its_own_line_of_work() -> None:
    llm = FakeLLM(answer((1, "yes", [3])), relevance=fits(jobs=[1]))
    result = judge_skills(PROFILE, "Developers", ["debug software"], [], llm, unrelated)
    assert result.required[0].level == "yes"
    assert result.required[0].evidence == ["Job title: Developer"]


def test_an_unrelated_job_title_cant_show_a_skill() -> None:
    llm = FakeLLM(answer((1, "partly", [3])), relevance=fits())
    result = judge_skills(PROFILE, "Lawyers", ["represent clients"], [], llm, unrelated)
    assert result.required[0].level == "no"
    assert result.required[0].evidence == []


def test_other_evidence_survives_when_an_unrelated_job_is_dropped() -> None:
    llm = FakeLLM(answer((1, "yes", [3, 1])), relevance=fits())
    result = judge_skills(PROFILE, "Analysts", ["programming"], [], llm, unrelated)
    assert result.required[0].level == "yes"
    assert result.required[0].evidence == ["Skill: Python"]


def test_a_degree_can_be_cited_as_evidence() -> None:
    llm = FakeLLM(answer((1, "yes", [5])), relevance=fits())
    result = judge_skills(PROFILE, "Developers", ["programming"], [], llm, unrelated)
    assert result.required[0].evidence == ["Degree: BSc Computing"]


# --- Related skills ---


def embed_with(similar_to: dict[str, str]) -> Any:
    """Gives each text its own direction, except pairs that should match exactly."""

    def embed(texts: list[str]) -> list[list[float]]:
        axes = sorted({similar_to.get(text, text) for text in texts})
        return [[float(axis == similar_to.get(text, text)) for axis in axes] for text in texts]

    return embed


def test_a_close_skill_the_model_missed_counts_partly() -> None:
    llm = FakeLLM(answer((1, "no", [])))
    result = judge_skills(PROFILE, "Developers", ["databases"], [], llm, embed_with({"databases": "SQL"}))
    assert result.required[0].level == "partly"
    assert result.required[0].evidence == ["Skill: SQL (a related skill)"]


def test_an_unrelated_skill_stays_not_shown() -> None:
    llm = FakeLLM(answer((1, "no", [])))
    assert judge_skills(PROFILE, "Developers", ["welding"], [], llm, unrelated).required[0].level == "no"


def test_similarity_never_changes_what_the_model_credited() -> None:
    llm = FakeLLM(answer((1, "yes", [1]), (2, "partly", [2])))
    result = judge_skills(PROFILE, "Developers", ["a", "b"], [], llm, no_embedding)
    assert [skill.level for skill in result.required] == ["yes", "partly"]


def test_no_own_skills_means_nothing_to_compare() -> None:
    bare = PROFILE.model_copy(update={"skills": [], "projects": []})
    llm = FakeLLM(answer((1, "no", [])))
    assert judge_skills(bare, "Developers", ["a"], [], llm, no_embedding).required[0].level == "no"


def test_similarity_just_below_the_line_does_not_count() -> None:
    def embed(texts: list[str]) -> list[list[float]]:
        below = MIN_RELATED_SIMILARITY - 0.01
        close = [below, (1 - below**2) ** 0.5]
        return [close if text == "databases" else [1.0, 0.0] for text in texts]

    llm = FakeLLM(answer((1, "no", [])))
    assert judge_skills(PROFILE, "Developers", ["databases"], [], llm, embed).required[0].level == "no"


@pytest.mark.skipif(
    not os.environ.get("RUN_EMBEDDING_TESTS"), reason="RUN_EMBEDDING_TESTS not set"
)
def test_real_embeddings_credit_close_skills_only() -> None:
    from app.embeddings import embed_texts

    welder = PROFILE.model_copy(deep=True)
    welder.skills[0].name_en = "MIG welding"
    welder.skills[1].name_en = "Bookkeeping"
    welder.projects = []
    llm = FakeLLM(answer((1, "no", []), (2, "no", [])))
    result = judge_skills(
        welder, "Welders", ["use welding equipment", "provide nursing care"], [], llm, embed_texts
    )
    assert result.required[0].level == "partly"
    assert "MIG welding" in result.required[0].evidence[0]
    assert result.required[1].level == "no"


# --- Saved judgements ---


def test_key_is_stable_for_the_same_input() -> None:
    assert judgement_key(PROFILE, "Developers", ["a"], [], "m") == judgement_key(PROFILE, "Developers", ["a"], [], "m")


def test_key_changes_with_anything_that_shapes_the_answer() -> None:
    base = judgement_key(PROFILE, "Developers", ["a"], ["b"], "m")
    other_jobs = PROFILE.model_copy(update={"work_history": []})
    for changed in (
        judgement_key(PROFILE, "Developers", ["a"], ["b"], "other"),
        judgement_key(PROFILE, "Developers", ["a"], ["c"], "m"),
        judgement_key(PROFILE, "Testers", ["a"], ["b"], "m"),
        judgement_key(PROFILE, "Developers", ["a", "b"], [], "m"),
        judgement_key(other_jobs, "Developers", ["a"], ["b"], "m"),
    ):
        assert changed != base
