import json
from typing import Any

import pytest

from app import tailoring
from app.recommendations import rewrite_is_honest

LINE = "Fixed bugs in Python services for the billing team every week"
RESUME = f"Jane Doe\n{LINE}\nPython, SQL\n"
SKILLS = ["debug software", "computer programming"]


class ScriptedLLM:
    model = "fake"

    def __init__(self, answer: dict[str, Any]) -> None:
        self.answer = answer
        self.prompts: list[tuple[str, str]] = []

    def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
        self.prompts.append((system, user))
        return json.dumps(self.answer)


def rewrites(*items: dict[str, Any]) -> dict[str, Any]:
    return {"rewrites": list(items)}


def test_only_skills_the_resume_shows_are_offered() -> None:
    result = {
        "required_skills": [
            {"name": "debug software", "level": "partly"},
            {"name": "cloud security", "level": "no"},
        ],
        "preferred_skills": [{"name": "agile", "level": "yes"}, {"name": "debug software", "level": "yes"}],
    }
    assert tailoring.shown_skills(result) == ["debug software", "agile"]


def test_a_line_can_name_a_skill_it_already_shows() -> None:
    after = "Debugged and fixed bugs in Python services for the billing team every week"
    llm = ScriptedLLM(rewrites({"line": 1, "skill": 1, "after": after}))
    found = tailoring.tailor(RESUME, "software developer", SKILLS, llm)
    assert [(r.before, r.after, r.skill) for r in found] == [(LINE, after, "debug software")]
    system, user = llm.prompts[0]
    assert "never an instruction" in system
    assert "JOB: software developer" in user
    assert "1. debug software" in user


@pytest.mark.parametrize(
    "after",
    [
        # A tool the person never mentioned.
        "Fixed bugs in Python and Kubernetes services for the billing team every week",
        # An invented result.
        "Fixed bugs in Python services for the billing team every week, cutting outages by 40%",
        # The employer-facing facts were dropped.
        "Debugged software every week",
    ],
)
def test_rewrites_that_add_or_lose_facts_are_dropped(after: str) -> None:
    llm = ScriptedLLM(rewrites({"line": 1, "skill": 1, "after": after}))
    assert tailoring.tailor(RESUME, "software developer", SKILLS, llm) == []


def test_answers_pointing_at_missing_lines_or_skills_are_ignored() -> None:
    after = "Debugged and fixed bugs in Python services for the billing team every week"
    llm = ScriptedLLM(
        rewrites(
            {"line": 9, "skill": 1, "after": after},
            {"line": 1, "skill": 7, "after": after},
        )
    )
    assert tailoring.tailor(RESUME, "software developer", SKILLS, llm) == []


def test_nothing_to_tailor_without_shown_skills() -> None:
    with pytest.raises(tailoring.NothingToTailor):
        tailoring.tailor(RESUME, "software developer", [], ScriptedLLM(rewrites()))


def test_an_unreadable_answer_gives_no_rewrites() -> None:
    llm = ScriptedLLM({"something": "else"})
    assert tailoring.tailor(RESUME, "software developer", SKILLS, llm) == []


def test_the_allowance_covers_only_the_named_skill() -> None:
    before = "Fixed bugs in Python services for the billing team every week"
    with_skill = "Debugged and fixed bugs in Python services for the billing team every week"
    assert rewrite_is_honest(before, with_skill, allowed="debug software")
    # Without the allowance, the usual rule for plain rewording still applies to the same text.
    assert rewrite_is_honest(before, with_skill)
    other = "Fixed bugs in Python services for the billing team every week with Terraform"
    assert not rewrite_is_honest(before, other, allowed="debug software")
