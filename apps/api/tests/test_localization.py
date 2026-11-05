import json
import re
from copy import deepcopy
from datetime import date
from typing import Any

import pytest

from app.localization import localized_evidence, localized_score, saved_names, translate_terms
from app.messages import catalogue_keys, region_name, say, weeks, years
from app.profile_schema import ExtractedProfile
from app.recommendations import build_plan, build_report, find_gaps, suggest_actions
from app.scoring import JudgedSkill, MarketSnapshot, ScoreInput, score_profile
from tests.helpers import VALID_PROFILE
from tests.test_recommendations import gap, suggested


class FakeLLM:
    model = "fake-model"

    def __init__(self, actions: Any = None, translate: bool = True) -> None:
        self.actions = actions if actions is not None else {"actions": []}
        self.translate = translate
        self.messages: list[str] = []

    def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
        self.messages.append(user)
        properties = schema["properties"]
        if "actions" in properties:
            return json.dumps(self.actions)
        if "rewrites" in properties:
            return json.dumps({"rewrites": []})
        terms = re.findall(r"^(\d+)\. (.+)$", user, re.MULTILINE)
        return json.dumps(
            {
                "translations": [
                    {"number": int(number), "text": f"перевод {term}" if self.translate else term}
                    for number, term in terms
                ]
            }
        )


class Terms:
    def __init__(self, known: dict[str, str] | None = None) -> None:
        self.known = dict(known or {})
        self.saved: list[dict[str, str]] = []

    def get_translations(self, terms: list[str], language: str) -> dict[str, str]:
        return {term: self.known[term] for term in terms if term in self.known}

    def save_translations(self, translations: dict[str, str], language: str) -> None:
        self.saved.append(translations)
        self.known.update(translations)


MARKET = MarketSnapshot(
    occupation_code="31301",
    occupation_name="Registered nurses",
    region="Ontario",
    sample_size=50,
    education={"Bachelor's degree": 8},
    experience={"3 years to less than 5 years": 8},
    salary={
        "p25": 70_000,
        "median": 85_000,
        "p75": 100_000,
        "currency": "CAD",
        "period": "yearly",
        "sample_size": 200,
        "region": "Ontario",
        "confidence": "high",
        "concentrated": True,
    },
    used_national_requirements=True,
)
LATIN_WORD = re.compile(r"\b(?!CAD\b|AWS\b|Developer\b|Python\b)[A-Za-z]{3,}\b")


def make_input(language: str = "ru", **changes: Any) -> ScoreInput:
    values: dict[str, Any] = {
        "profile": ExtractedProfile.model_validate(deepcopy(VALID_PROFILE)),
        "market": MARKET,
        "required": [
            JudgedSkill(name="nursing care", level="yes", evidence=["Skill: Python"]),
            JudgedSkill(name="triage", level="partly", evidence=["Job title: Developer"]),
            JudgedSkill(name="wound care", level="no", evidence=[]),
        ],
        "preferred": [JudgedSkill(name="research", level="no", evidence=[])],
        "relevant_job_indexes": [0],
        "relevant_credential_indexes": [],
        "portfolio_links": 0,
        "as_of": date(2026, 11, 5),
        "language": language,
    }
    return ScoreInput(**{**values, **changes})


def test_both_languages_have_every_message() -> None:
    assert catalogue_keys("en") == catalogue_keys("ru")


@pytest.mark.parametrize("key", sorted(catalogue_keys("ru")))
def test_every_russian_message_has_the_same_placeholders(key: str) -> None:
    fields = re.compile(r"\{(\w+)\}")
    assert set(fields.findall(say_raw("en", key))) == set(fields.findall(say_raw("ru", key)))


def say_raw(language: str, key: str) -> str:
    from app import messages

    return messages._CATALOGUE[language][key]


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (1, "1 год"),
        (2, "2 года"),
        (4, "4 года"),
        (5, "5 лет"),
        (11, "11 лет"),
        (12, "12 лет"),
        (14, "14 лет"),
        (21, "21 год"),
        (22, "22 года"),
        (25, "25 лет"),
        (1.5, "1,5 года"),
        (0, "0 лет"),
    ],
)
def test_russian_years_read_properly(value: float, text: str) -> None:
    assert years("ru", value) == text


@pytest.mark.parametrize(("value", "text"), [(1, "1 неделя"), (3, "3 недели"), (12, "12 недель"), (21, "21 неделя")])
def test_russian_weeks_read_properly(value: int, text: str) -> None:
    assert weeks("ru", value) == text


def test_english_is_unchanged_by_a_russian_catalogue() -> None:
    assert years("en", 1) == "1 year"
    assert years("en", 2.5) == "2.5 years"
    assert weeks("en", 1) == "1 week"
    assert say("en", "not_weighed", label="Portfolio") == "Portfolio: not usually weighed in this field."


def test_region_names_are_translated() -> None:
    assert region_name("ru", "Ontario") == "Онтарио"
    assert region_name("en", "Ontario") == "Ontario"
    assert region_name("ru", "Atlantis") == "Atlantis"


# --- The score ---


def test_the_score_is_the_same_in_every_language() -> None:
    english = score_profile(make_input("en"))
    russian = score_profile(make_input("ru"))
    assert russian.score == english.score
    assert [c.points for c in russian.categories] == [c.points for c in english.categories]
    assert russian.salary is not None and english.salary is not None
    assert russian.salary.low == english.salary.low


def test_a_russian_score_is_written_in_russian() -> None:
    result = score_profile(make_input("ru"))
    written = [
        *(c.label for c in result.categories),
        *(c.reason for c in result.categories),
        *result.confidence.reasons,
        *result.not_scored,
        result.weights_used,
        result.disclaimer,
        result.salary.basis if result.salary else "",
    ]
    for text in written:
        assert not LATIN_WORD.search(text), text


def test_english_stays_english() -> None:
    result = score_profile(make_input("en"))
    assert not re.search(r"[А-Яа-я]", json.dumps(result.model_dump(), ensure_ascii=False))


# --- Translating official names ---


def test_english_never_asks_the_ai_or_the_database() -> None:
    llm = FakeLLM()
    assert translate_terms(["triage"], "en", llm, None) == {}  # type: ignore[arg-type]
    assert saved_names(["triage"], "en", None) == {}  # type: ignore[arg-type]
    assert llm.messages == []


def test_new_names_are_translated_once_and_kept() -> None:
    llm, terms = FakeLLM(), Terms()
    first = translate_terms(["triage", "triage", "wound care"], "ru", llm, terms)
    assert first == {"triage": "перевод triage", "wound care": "перевод wound care"}
    assert len(llm.messages) == 1
    assert translate_terms(["triage", "wound care"], "ru", llm, terms) == first
    assert len(llm.messages) == 1


def test_only_missing_names_are_sent() -> None:
    llm, terms = FakeLLM(), Terms({"triage": "сортировка"})
    translate_terms(["triage", "wound care"], "ru", llm, terms)
    assert "triage" not in llm.messages[0]
    assert "wound care" in llm.messages[0]


def test_long_lists_go_in_batches() -> None:
    llm, terms = FakeLLM(), Terms()
    found = translate_terms([f"skill {n}" for n in range(65)], "ru", llm, terms)
    assert len(found) == 65
    assert len(llm.messages) == 3


def test_an_untranslated_answer_isnt_saved() -> None:
    llm, terms = FakeLLM(translate=False), Terms()
    assert translate_terms(["wound care"], "ru", llm, terms) == {}
    assert terms.saved == []


def test_product_names_can_stay_as_they_are() -> None:
    class SameName(FakeLLM):
        def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
            return json.dumps({"translations": [{"number": 1, "text": "Jenkins"}]})

    assert translate_terms(["Jenkins"], "ru", SameName(), Terms()) == {"Jenkins": "Jenkins"}


def test_an_occupation_handed_back_in_english_isnt_saved() -> None:
    class SameName(FakeLLM):
        def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
            return json.dumps({"translations": [{"number": 1, "text": "Data scientists"}]})

    terms = Terms()
    assert translate_terms(["Data scientists"], "ru", SameName(), terms) == {}
    assert terms.saved == []


def test_invalid_answers_leave_the_english_name() -> None:
    class Broken(FakeLLM):
        def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
            return "not json"

    assert translate_terms(["triage"], "ru", Broken(), Terms()) == {}


def test_saved_names_never_use_the_ai() -> None:
    terms = Terms({"triage": "сортировка"})
    assert saved_names(["triage", "wound care", "triage"], "ru", terms) == {"triage": "сортировка"}


@pytest.mark.parametrize(
    ("item", "text"),
    [
        ("Skill: Python", "Навык: Python"),
        ("Job title: Developer", "Должность: Developer"),
        ("Project: Ledger (Python)", "Проект: Ledger (Python)"),
        ("Degree: BSc Computing", "Образование: BSc Computing"),
        ("Certification: AWS Developer", "Сертификат: AWS Developer"),
        ("Skill: SQL (a related skill)", "Навык: SQL (связанный навык)"),
    ],
)
def test_evidence_labels_are_translated(item: str, text: str) -> None:
    assert localized_evidence(item, "ru") == text
    assert localized_evidence(item, "en") == item


def test_a_score_is_shown_with_translated_names() -> None:
    llm, terms = FakeLLM(), Terms()
    result = localized_score(score_profile(make_input("ru")), "ru", llm, terms)
    assert result.occupation_name == "перевод Registered nurses"
    assert result.required_skills[0].name == "перевод nursing care"
    assert result.required_skills[0].evidence == ["Навык: Python"]
    assert result.required_skills[1].evidence == ["Должность: Developer"]
    assert result.preferred_skills[0].name == "перевод research"


def test_english_scores_skip_translation_entirely() -> None:
    original = score_profile(make_input("en"))
    llm = FakeLLM()
    assert localized_score(original, "en", llm, None) is original  # type: ignore[arg-type]
    assert llm.messages == []


# --- The report ---


def test_a_russian_request_asks_the_ai_for_russian() -> None:
    llm = FakeLLM()
    suggest_actions(make_input("ru"), [gap()], llm)
    assert 'in Russian' in llm.messages[0]
    english = FakeLLM()
    suggest_actions(make_input("en"), [gap()], english)
    assert 'in Russian' not in english.messages[0]


def test_steps_left_in_english_fall_back_for_a_russian_reader() -> None:
    llm = FakeLLM({"actions": [suggested()]})
    action = suggest_actions(make_input("ru"), [gap("triage")], llm, {"triage": "сортировка"})[0]
    assert action.title == "Развивайте навык: сортировка"
    assert action.gap == "сортировка"


def test_steps_in_russian_are_kept() -> None:
    answer = suggested(title="Основы учёта", details="Научитесь вести записи.", expected_result="Навык учёта.")
    action = suggest_actions(make_input("ru"), [gap()], FakeLLM({"actions": [answer]}))[0]
    assert action.title == "Основы учёта"


@pytest.mark.parametrize(
    "text",
    ["Это повысит шансы на 40 процентов", "Статистика показывает пользу", "Мы гарантируем работу", "В среднем это месяц", "Пройдите «Курс 101»"],
)
def test_invented_details_in_russian_are_rejected(text: str) -> None:
    llm = FakeLLM({"actions": [suggested(details=text)]})
    assert suggest_actions(make_input("ru"), [gap("triage")], llm)[0].title.startswith("Развивайте навык")


def test_gap_details_and_titles_are_in_russian() -> None:
    data = make_input("ru", portfolio_links=0)
    for item in find_gaps(data, score_profile(data)):
        assert not LATIN_WORD.search(item.detail.replace("Developer", "")), item.detail


def test_a_russian_plan_reads_in_russian() -> None:
    action = suggest_actions(make_input("ru"), [gap("уход")], FakeLLM())[0]
    plan = build_plan([action], True, "ru")
    assert plan.thirty_days[0].startswith("Обновите резюме")
    assert "примерно 4 недели" in plan.thirty_days[1]
    assert "новый анализ" in plan.ninety_days[-1]


def test_the_whole_report_comes_back_in_russian() -> None:
    data = make_input("ru")

    def no_alternatives(*_args: Any) -> list[Any]:
        return []

    report = build_report(
        data=data,
        result=score_profile(data),
        extraction={"data": deepcopy(VALID_PROFILE)},
        resume_text=None,
        document_id="doc",
        user_id="user",
        region="Ontario",
        as_of=data.as_of,
        store=Terms(),  # type: ignore[arg-type]
        llm=FakeLLM(),
        embed=lambda texts: [[1.0] for _ in texts],
        alternatives_finder=no_alternatives,
    )
    titles = [item.title for item in report.gaps]
    assert "перевод wound care" in titles
    assert report.actions[0].gap in titles
    for note in report.notes:
        assert not LATIN_WORD.search(note), note
