import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.routers import market
from scripts import build_occupation_map as mapper
from scripts.seed_market import (
    MAX_PREFERRED_SKILLS,
    all_occupation_rows,
    occupation_skill_rows,
    rank_by_relevance,
)
from tests.helpers import auth_headers

STATS = {
    "sample_size": 120,
    "salary_sample_size": 110,
    "salary_p25": 60000.4,
    "salary_median": 70000.6,
    "salary_p75": 81000.2,
    "salary_top_share": 0.1,
    "latest_posting": "2026-10-30",
    "education": {"Bachelor's degree": 12},
    "experience": {"5 years or more": 3},
}


class FakeMarket:
    def __init__(self) -> None:
        self.match: dict[str, Any] | None = {
            "title": "accountant",
            "occupation_code": "11100",
            "occupation_name": "Financial auditors and accountants",
            "similarity": 0.98,
        }
        self.stats: dict[str | None, dict[str, Any]] = {None: STATS, "Ontario": STATS}
        self.skills = [
            {"required": True, "rank": 0, "skills": {"name": "accounting techniques", "esco_id": "e/1"}},
            {"required": False, "rank": 0, "skills": {"name": "perform risk analysis", "esco_id": "e/2"}},
        ]
        self.stat_calls: list[tuple[str, str | None]] = []

    def match_occupation(self, _embedding: list[float]) -> dict[str, Any] | None:
        return self.match

    def market_stats(self, code: str, region: str | None) -> dict[str, Any]:
        self.stat_calls.append((code, region))
        return self.stats[region]

    def occupation_skills(self, _code: str) -> list[dict[str, Any]]:
        return self.skills


@pytest.fixture
def fake_market(monkeypatch: pytest.MonkeyPatch) -> FakeMarket:
    fake = FakeMarket()
    monkeypatch.setattr(market, "store", fake)
    monkeypatch.setattr("app.embeddings.embed_texts", lambda texts: [[0.1] for _ in texts])
    return fake


def get(client: TestClient, **params: str) -> Any:
    return client.get("/market/requirements", params=params, headers=auth_headers())


def test_returns_salary_skills_and_sample_size(client: TestClient, fake_market: FakeMarket) -> None:
    response = get(client, role="Accountant", region="Ontario")
    assert response.status_code == 200
    body = response.json()
    assert body["occupationCode"] == "11100"
    assert body["region"] == "Ontario"
    assert body["sampleSize"] == 120
    assert body["salary"] == {
        "p25": 60000,
        "median": 70001,
        "p75": 81000,
        "currency": "CAD",
        "period": "yearly",
        "sampleSize": 110,
        "region": "Ontario",
        "confidence": "high",
        "concentrated": False,
    }
    assert body["requiredSkills"] == ["accounting techniques"]
    assert body["preferredSkills"] == ["perform risk analysis"]
    assert body["latestPosting"] == "2026-10-30"


def test_response_credits_sources_and_states_limits(client: TestClient, fake_market: FakeMarket) -> None:
    body = get(client, role="Accountant").json()
    assert "Open Government Licence" in body["sources"][0]
    assert "ESCO" in body["sources"][1]
    assert "not a count" in body["limitations"]


def test_requires_auth(client: TestClient, fake_market: FakeMarket) -> None:
    assert client.get("/market/requirements", params={"role": "Accountant"}).status_code == 401


def test_no_region_means_national(client: TestClient, fake_market: FakeMarket) -> None:
    body = get(client, role="Accountant").json()
    assert body["region"] == "Canada"
    assert fake_market.stat_calls == [("11100", None)]


@pytest.mark.parametrize("region", ["on", "ON", "ontario", " Ontario "])
def test_region_spellings_are_understood(
    client: TestClient, fake_market: FakeMarket, region: str
) -> None:
    assert get(client, role="Accountant", region=region).json()["region"] == "Ontario"


def test_quebec_works_with_or_without_the_accent(client: TestClient, fake_market: FakeMarket) -> None:
    fake_market.stats["Québec"] = STATS
    assert get(client, role="Accountant", region="quebec").json()["region"] == "Québec"


def test_unknown_region_is_explained(client: TestClient, fake_market: FakeMarket) -> None:
    response = get(client, role="Accountant", region="Atlantis")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unknown_region"


@pytest.mark.parametrize(
    "match",
    [
        None,
        {"title": "accountant", "occupation_code": "1", "occupation_name": "X", "similarity": 0.5},
        # A high score alone isn't trusted, since "Jotai" scored 0.90 against "Grovo".
        {"title": "zzz", "occupation_code": "1", "occupation_name": "yyy", "similarity": 0.99},
    ],
)
def test_unrecognised_role_is_refused_rather_than_guessed(
    client: TestClient, fake_market: FakeMarket, match: dict[str, Any] | None
) -> None:
    fake_market.match = match
    response = get(client, role="Accountant")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "role_not_found"


def test_shared_word_with_the_occupation_name_also_counts(
    client: TestClient, fake_market: FakeMarket
) -> None:
    fake_market.match = {
        "title": "something else",
        "occupation_code": "11100",
        "occupation_name": "Financial auditors",
        "similarity": 0.9,
    }
    assert get(client, role="auditor").status_code == 200


@pytest.mark.parametrize(
    ("size", "expected"), [(5, "low"), (29, "low"), (30, "medium"), (99, "medium"), (100, "high")]
)
def test_confidence_follows_sample_size(
    client: TestClient, fake_market: FakeMarket, size: int, expected: str
) -> None:
    fake_market.stats[None] = {**STATS, "salary_sample_size": size}
    assert get(client, role="Accountant").json()["salary"]["confidence"] == expected


def test_one_repeated_pay_figure_lowers_confidence_and_is_flagged(
    client: TestClient, fake_market: FakeMarket
) -> None:
    fake_market.stats[None] = {**STATS, "salary_sample_size": 354, "salary_top_share": 1.0}
    salary = get(client, role="Accountant").json()["salary"]
    assert salary["concentrated"] is True
    assert salary["confidence"] == "low"


def test_exactly_half_sharing_one_figure_is_not_flagged(
    client: TestClient, fake_market: FakeMarket
) -> None:
    fake_market.stats[None] = {**STATS, "salary_top_share": 0.5}
    assert get(client, role="Accountant").json()["salary"]["concentrated"] is False


def test_thin_regional_data_falls_back_to_national_and_says_so(
    client: TestClient, fake_market: FakeMarket
) -> None:
    fake_market.stats["Yukon"] = {**STATS, "sample_size": 3, "salary_sample_size": 3}
    body = get(client, role="Accountant", region="Yukon").json()
    assert body["region"] == "Yukon"
    assert body["sampleSize"] == 3
    assert body["salary"]["region"] == "Canada"
    assert body["salary"]["sampleSize"] == 110


def test_no_salary_data_at_all_is_reported_as_none(client: TestClient, fake_market: FakeMarket) -> None:
    empty = {
        **STATS,
        "sample_size": 0,
        "salary_sample_size": 0,
        "salary_p25": None,
        "salary_median": None,
        "salary_p75": None,
    }
    fake_market.stats[None] = empty
    assert get(client, role="Accountant").json()["salary"] is None


def test_occupation_without_linked_skills_returns_empty_lists(
    client: TestClient, fake_market: FakeMarket
) -> None:
    fake_market.skills = []
    body = get(client, role="Accountant").json()
    assert body["requiredSkills"] == []
    assert body["preferredSkills"] == []


class ScriptedLLM:
    model = "fake"

    def __init__(self, *outputs: str) -> None:
        self.outputs = list(outputs)
        self.user = ""

    def complete_json(self, system: str, user: str, schema: dict, attempt: int = 0) -> str:
        self.user = user
        return self.outputs.pop(0)


OCCUPATION = {"code": "72400", "name": "Millwrights", "titles": ["millwright"]}
CANDIDATES = [
    {"uri": "esco/milliner", "title": "milliner", "description": "Designs hats.", "score": 0.81},
    {"uri": "esco/fitter", "title": "industrial machinery mechanic", "description": "Repairs machines.", "score": 0.7},
]


def test_ai_choice_is_not_just_the_highest_similarity() -> None:
    match = mapper.choose_match(OCCUPATION, CANDIDATES, ScriptedLLM('{"choice": 2}'))
    assert match["uri"] == "esco/fitter"


def test_ai_can_say_none_match() -> None:
    assert mapper.choose_match(OCCUPATION, CANDIDATES, ScriptedLLM('{"choice": 0}')) is None


def test_candidate_descriptions_reach_the_ai() -> None:
    llm = ScriptedLLM('{"choice": 1}')
    mapper.choose_match(OCCUPATION, CANDIDATES, llm)
    assert "Designs hats." in llm.user
    assert "millwright" in llm.user


@pytest.mark.parametrize("bad", ['{"choice": 99}', "not json"])
def test_unusable_answers_are_retried_then_treated_as_none(bad: str) -> None:
    assert mapper.choose_match(OCCUPATION, CANDIDATES, ScriptedLLM(bad, bad)) is None


def test_retry_can_recover() -> None:
    match = mapper.choose_match(OCCUPATION, CANDIDATES, ScriptedLLM("not json", '{"choice": 1}'))
    assert match["uri"] == "esco/milliner"


def test_occupation_summary_keeps_what_later_steps_need() -> None:
    summary = mapper.summarize_occupation(
        {
            "uri": "esco/x",
            "title": "cook",
            "alternativeLabel": {"en": ["chef de partie"], "fr": ["cuisinier"]},
            "description": {"en": {"literal": "Cooks food."}},
            "_links": {
                "hasEssentialSkill": [{"uri": "s/1", "title": "use cooking techniques"}],
                "hasOptionalSkill": [{"uri": "s/2", "title": "plan menus"}],
            },
        }
    )
    assert summary["alternatives"] == ["chef de partie"]
    assert summary["description"] == "Cooks food."
    assert summary["essential_skills"] == ["s/1"]
    assert summary["optional_skills"] == [{"uri": "s/2", "title": "plan menus"}]


def test_summary_handles_missing_fields() -> None:
    summary = mapper.summarize_occupation({"uri": "esco/x", "title": "cook"})
    assert summary["alternatives"] == []
    assert summary["essential_skills"] == []


def esco_client(handler: Any) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_esco_server_errors_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapper, "RETRY_BASE_SECONDS", 0)
    replies = [httpx.Response(500), httpx.Response(429), httpx.Response(200, json={"ok": True})]
    with esco_client(lambda _request: replies.pop(0)) as client:
        assert mapper._get_json(client, mapper.DETAIL_URL) == {"ok": True}


def test_esco_network_errors_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapper, "RETRY_BASE_SECONDS", 0)
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("slow")
        return httpx.Response(200, json={"ok": True})

    with esco_client(handler) as client:
        assert mapper._get_json(client, mapper.DETAIL_URL) == {"ok": True}


def test_esco_gives_up_after_the_attempt_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapper, "RETRY_BASE_SECONDS", 0)
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with esco_client(handler) as client, pytest.raises(httpx.HTTPStatusError):
        mapper._get_json(client, mapper.DETAIL_URL)
    assert len(calls) == mapper.FETCH_ATTEMPTS


def test_esco_not_found_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mapper, "RETRY_BASE_SECONDS", 0)
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    with esco_client(handler) as client, pytest.raises(httpx.HTTPStatusError):
        mapper._get_json(client, mapper.DETAIL_URL)
    assert len(calls) == 1


def test_esco_refuses_another_host() -> None:
    with esco_client(lambda _request: httpx.Response(200)) as client, pytest.raises(RuntimeError):
        mapper._get_json(client, "https://evil.example/x")


def test_records_failing_on_the_default_version_use_the_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mapper, "RETRY_BASE_SECONDS", 0)
    versions: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        version = request.url.params.get("selectedVersion")
        versions.append(version)
        if version is None:
            return httpx.Response(500)
        return httpx.Response(200, json={"uri": "esco/civil", "title": "civil engineer"})

    with esco_client(handler) as client:
        assert mapper.fetch_occupation(client, "esco/civil")["title"] == "civil engineer"
    assert versions[-1] == mapper.FALLBACK_VERSION


def load_map() -> dict[str, dict[str, Any]]:
    return {row["code"]: row for row in json.loads(mapper.MAP_PATH.read_text(encoding="utf-8"))}


def test_map_entries_are_complete() -> None:
    rows = load_map()
    assert len(rows) >= 490
    for row in rows.values():
        assert row["code"] and row["name"]
        assert bool(row["esco_uri"]) == bool(row["esco_title"])


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("11100", "accountant"),
        ("21232", "software developer"),
        ("21300", "civil engineer"),
        ("31301", "nurse responsible for general care"),
        ("32101", "nurse assistant"),
        ("33100", "dental chairside assistant"),
        ("41220", "secondary school teacher"),
        ("63200", "cook"),
        ("65200", "waiter/waitress"),
        ("72106", "welder"),
        ("72400", "industrial machinery mechanic"),
    ],
)
def test_important_occupations_link_to_the_right_esco_entry(code: str, expected: str) -> None:
    assert load_map()[code]["esco_title"] == expected


@pytest.mark.parametrize(
    ("code", "wrong"),
    [
        ("72400", "milliner"),
        ("65200", "food and beverage packaging technologist"),
        ("73111", "glass-blower"),
        ("92022", "footwear assembly supervisor"),
        ("53121", "circus artist"),
        ("21300", "installation engineer"),
    ],
)
def test_known_wrong_links_stay_gone(code: str, wrong: str) -> None:
    assert load_map()[code]["esco_title"] != wrong


def fake_vectors(monkeypatch: pytest.MonkeyPatch, by_text: dict[str, list[float]]) -> None:
    monkeypatch.setattr(
        "scripts.seed_market.embed_texts", lambda texts: [by_text[text] for text in texts]
    )


def test_skills_rank_by_closeness_to_the_occupation(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_vectors(
        monkeypatch,
        {"accountant": [1, 0], "film production process": [0, 1], "manage accounts": [1, 0.1]},
    )
    assert rank_by_relevance("accountant", ["film production process", "manage accounts"]) == [1, 0]


def test_occupations_with_no_ads_this_month_are_still_stored() -> None:
    rows = all_occupation_rows(
        {"21332": {"name": "Petroleum engineers", "esco_uri": "e/1", "esco_title": "petroleum engineer"}}
    )
    assert rows == [
        {"code": "21332", "name": "Petroleum engineers", "esco_uri": "e/1", "esco_title": "petroleum engineer"}
    ]


def test_no_skills_to_rank_needs_no_embedding() -> None:
    assert rank_by_relevance("accountant", []) == []


def test_preferred_skills_are_capped_and_required_ones_win(monkeypatch: pytest.MonkeyPatch) -> None:
    total = MAX_PREFERRED_SKILLS + 5
    optional = [{"uri": f"o/{i}", "title": f"optional {i}"} for i in range(total)]
    vectors = {"accountant": [1.0, 0.0], "core": [1.0, 0.0]}
    vectors.update({f"optional {i}": [1.0, float(i + 1)] for i in range(total)})
    fake_vectors(monkeypatch, vectors)

    occupation = {
        "title": "accountant",
        "essential_skills": ["e/core", "e/not-loaded"],
        "optional_skills": [*optional, {"uri": "e/core", "title": "core"}],
    }
    ids = {"e/core": "id-core", **{f"o/{i}": f"id-{i}" for i in range(total)}}
    rows = occupation_skill_rows("11100", occupation, ids, {"e/core": "core"})

    required = [row for row in rows if row["required"]]
    preferred = [row for row in rows if not row["required"]]
    assert [row["skill_id"] for row in required] == ["id-core"]
    assert len(preferred) <= MAX_PREFERRED_SKILLS
    assert "id-19" not in {row["skill_id"] for row in preferred}
