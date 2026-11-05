import json
from copy import deepcopy
from datetime import date
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

from app import analysis, tasks
from app.llm import LLMUnavailable
from app.routers import analyses
from tests.helpers import OTHER_USER_ID, USER_ID, VALID_PROFILE, FakeStore, auth_headers

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
MATCH = {
    "occupation_code": "21232",
    "occupation_name": "Software developers and programmers",
    "title": "software developer",
    "similarity": 0.97,
}
SKILLS = [
    {"required": True, "rank": 1, "skills": {"name": "computer programming", "esco_id": "a"}},
    {"required": True, "rank": 2, "skills": {"name": "debug software", "esco_id": "b"}},
    {"required": False, "rank": 3, "skills": {"name": "agile", "esco_id": "c"}},
]
SKILLS_ANSWER = {
    "judgements": [
        {"skill": 1, "level": "yes", "evidence": [1]},
        {"skill": 2, "level": "partly", "evidence": [3]},
        {"skill": 3, "level": "no", "evidence": []},
    ]
}
RELEVANCE_ANSWER = {
    "jobs": [{"job": 1, "fits": "yes"}],
    "education": [{"item": 1, "fits": "yes"}],
}


class FakeLLM:
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0
        self.error: Exception | None = None

    def complete_json(self, system: str, user: str, schema: dict[str, Any], attempt: int = 0) -> str:
        self.calls += 1
        if self.error:
            raise self.error
        return json.dumps(
            SKILLS_ANSWER if "judgements" in schema["properties"] else RELEVANCE_ANSWER
        )


class AnalysisFakeStore(FakeStore):
    def __init__(self) -> None:
        super().__init__()
        self.analyses: dict[str, dict[str, Any]] = {}
        self.judgements: dict[tuple[str, str], dict[str, Any]] = {}
        self.target_roles: list[dict[str, str]] = []
        self.market_error: Exception | None = None

    def match_occupation(self, _embedding: list[float]) -> dict[str, Any] | None:
        return MATCH

    def market_stats(self, _code: str, _region: str | None) -> dict[str, Any]:
        if self.market_error:
            raise self.market_error
        return STATS

    def occupation_skills(self, _code: str) -> list[dict[str, Any]]:
        return SKILLS

    def get_or_create_target_role(self, user_id: str, title: str, region: str) -> str:
        role = {"user_id": user_id, "title": title, "region": region}
        if role not in self.target_roles:
            self.target_roles.append(role)
        return str(self.target_roles.index(role))

    def insert_analysis(self, row: dict[str, Any]) -> dict[str, Any]:
        target = self.target_roles[int(row["target_role_id"])]
        stored = {
            "id": str(uuid4()),
            "status": "pending",
            "score": None,
            "result": None,
            "error_code": None,
            "created_at": "2026-11-04T00:00:00+00:00",
            "completed_at": None,
            "target_roles": {"title": target["title"], "region": target["region"]},
            **row,
        }
        self.analyses[stored["id"]] = stored
        return dict(stored)

    def get_analysis(self, analysis_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        row = self.analyses.get(analysis_id)
        if row is None or (user_id is not None and row["user_id"] != user_id):
            return None
        return dict(row)

    def list_analyses(self, user_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.analyses.values() if row["user_id"] == user_id]

    def update_analysis(self, analysis_id: str, fields: dict[str, Any]) -> None:
        self.analyses[analysis_id].update(fields)

    def get_skill_judgement(self, document_id: str, key: str) -> dict[str, Any] | None:
        return self.judgements.get((document_id, key))

    def save_skill_judgement(self, document_id: str, key: str, result: dict[str, Any]) -> None:
        self.judgements[(document_id, key)] = json.loads(json.dumps(result))


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[list[Any]] = []
        self.error: Exception | None = None

    def apply_async(self, args: list[Any], retry: bool = True) -> None:
        if self.error:
            raise self.error
        self.calls.append(args)


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> AnalysisFakeStore:
    fake = AnalysisFakeStore()
    monkeypatch.setattr(analyses, "store", fake)
    monkeypatch.setattr(tasks, "store", fake)
    monkeypatch.setattr("app.embeddings.embed_texts", lambda texts: [[0.1] * 3 for _ in texts])
    monkeypatch.setattr(tasks, "embed_texts", lambda texts: [[float(i == n) for n in range(len(texts))] for i in range(len(texts))])
    return fake


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(tasks, "get_llm", lambda: fake)
    return fake


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> FakeQueue:
    fake = FakeQueue()
    monkeypatch.setattr(analyses, "run_analysis", fake)
    return fake


def add_resume(store: AnalysisFakeStore, user_id: str = USER_ID, **changes: Any) -> str:
    row = store.insert_document(
        {
            "user_id": user_id,
            "type": "resume",
            "status": "ready",
            "extraction_status": "ready",
            **changes,
        }
    )
    store.save_extraction(
        row["id"], user_id, deepcopy(VALID_PROFILE), "v1", "m", False, False, [], []
    )
    return str(row["id"])


def start(client: TestClient, document_id: str, **changes: Any) -> Any:
    body = {"documentId": document_id, "role": "software developer", "region": "Ontario", **changes}
    return client.post("/analyses", json=body, headers=auth_headers())


def run(store: AnalysisFakeStore, queue: FakeQueue) -> str:
    args = queue.calls[-1]
    tasks.run_analysis.apply(args=args)
    return str(args[0])


# --- Starting ---


def test_starting_queues_the_job_and_saves_the_role(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    response = start(client, add_resume(store))
    assert response.status_code == 202
    analysis_id = response.json()["analysisId"]
    assert queue.calls == [[analysis_id, "21232", MATCH["occupation_name"], "Ontario"]]
    assert store.target_roles == [
        {"user_id": USER_ID, "title": "software developer", "region": "Ontario"}
    ]
    assert store.analyses[analysis_id]["status"] == "pending"


def test_the_same_role_isnt_saved_twice(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    document_id = add_resume(store)
    start(client, document_id)
    start(client, document_id)
    assert len(store.target_roles) == 1
    assert len(store.analyses) == 2


def test_no_region_means_all_of_canada(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    start(client, add_resume(store), region=None)
    assert queue.calls[0][3] is None
    assert store.target_roles[0]["region"] == "Canada"


def test_starting_requires_sign_in(client: TestClient, store: AnalysisFakeStore) -> None:
    body = {"documentId": str(uuid4()), "role": "software developer"}
    assert client.post("/analyses", json=body).status_code == 401


def test_cant_use_someone_elses_resume(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    response = start(client, add_resume(store, user_id=OTHER_USER_ID))
    assert response.status_code == 404
    assert queue.calls == []
    assert store.analyses == {}


def test_only_resumes_can_be_scored(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    response = start(client, add_resume(store, type="cover_letter"))
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_a_resume_still_being_read_cant_be_scored(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    response = start(client, add_resume(store, extraction_status="running"))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "resume_not_ready"
    assert queue.calls == []


def test_unknown_region_is_refused(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    response = start(client, add_resume(store), region="Atlantis")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "unknown_region"
    assert store.analyses == {}


def test_unrecognised_role_is_refused(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store, "match_occupation", lambda _embedding: None)
    response = start(client, add_resume(store), role="dragon tamer")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "role_not_found"


def test_a_queue_outage_is_reported_and_recorded(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    queue.error = OperationalError("down")
    response = start(client, add_resume(store))
    assert response.status_code == 503
    only = next(iter(store.analyses.values()))
    assert (only["status"], only["error_code"]) == ("failed", "queue_unavailable")


# --- Running ---


def test_a_finished_analysis_is_saved_with_its_breakdown(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    start(client, add_resume(store))
    analysis_id = run(store, queue)
    body = client.get(f"/analyses/{analysis_id}", headers=auth_headers()).json()
    assert body["status"] == "completed"
    assert body["role"] == "software developer"
    assert body["score"] == body["result"]["score"]
    assert 0 < body["score"] <= 100
    assert sum(c["points"] for c in body["result"]["categories"]) == body["score"]
    assert body["result"]["requiredSkills"][0] == {
        "name": "computer programming",
        "level": "yes",
        "evidence": ["Skill: Python"],
    }
    assert body["result"]["preferredSkills"][0]["name"] == "agile"
    assert body["result"]["salary"]["sampleSize"] == 150
    assert body["completedAt"]


def test_running_again_gives_the_same_score_without_asking_the_ai_again(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    document_id = add_resume(store)
    start(client, document_id)
    first = run(store, queue)
    start(client, document_id)
    second = run(store, queue)
    assert llm.calls == 2  # the skills question and the relevance question, once each
    assert store.analyses[first]["result"] == store.analyses[second]["result"]


def test_a_saved_judgement_survives_a_real_json_round_trip(
    store: AnalysisFakeStore, llm: FakeLLM
) -> None:
    document_id = add_resume(store)
    kwargs: dict[str, Any] = {
        "extraction": store.saved_extractions[document_id],
        "document_id": document_id,
        "user_id": USER_ID,
        "occupation_code": "21232",
        "occupation_name": "Developers",
        "region": "Ontario",
        "as_of": date(2026, 11, 4),
        "store": store,
        "llm": llm,
        "embed": lambda texts: [[float(i == n) for n in range(len(texts))] for i in range(len(texts))],
    }
    assert analysis.analyze(**kwargs) == analysis.analyze(**kwargs)
    assert llm.calls == 2


def test_a_different_role_asks_the_ai_again(
    store: AnalysisFakeStore, llm: FakeLLM
) -> None:
    document_id = add_resume(store)
    kwargs: dict[str, Any] = {
        "extraction": store.saved_extractions[document_id],
        "document_id": document_id,
        "user_id": USER_ID,
        "occupation_code": "21232",
        "region": None,
        "as_of": date(2026, 11, 4),
        "store": store,
        "llm": llm,
        "embed": lambda texts: [[float(i == n) for n in range(len(texts))] for i in range(len(texts))],
    }
    analysis.analyze(occupation_name="Developers", **kwargs)
    analysis.analyze(occupation_name="Testers", **kwargs)
    assert llm.calls == 4


def _analyze_in(store: AnalysisFakeStore, llm: FakeLLM, region: str | None) -> Any:
    document_id = add_resume(store)
    return analysis.analyze(
        extraction=store.saved_extractions[document_id],
        document_id=document_id,
        user_id=USER_ID,
        occupation_code="21232",
        occupation_name="Developers",
        region=region,
        as_of=date(2026, 11, 4),
        store=store,
        llm=llm,
        embed=lambda texts: [[float(i == n) for n in range(len(texts))] for i in range(len(texts))],
    )


def test_a_place_with_no_ads_gets_the_same_categories_as_anywhere_else(
    store: AnalysisFakeStore, llm: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    national = _analyze_in(store, llm, None)
    empty = {**STATS, "education": {}, "experience": {}, "sample_size": 0, "salary_sample_size": 0}
    monkeypatch.setattr(store, "market_stats", lambda _code, region: empty if region else STATS)
    local = _analyze_in(store, llm, "Nunavut")
    assert {c.key: c.points for c in local.categories} == {c.key: c.points for c in national.categories}
    assert local.score == national.score
    assert local.confidence.level == "low"
    assert any("all of Canada" in reason for reason in local.confidence.reasons)


def test_enough_local_ads_keep_their_own_requirements(
    store: AnalysisFakeStore, llm: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str | None] = []

    def stats(_code: str, region: str | None) -> dict[str, Any]:
        calls.append(region)
        return STATS

    monkeypatch.setattr(store, "market_stats", stats)
    result = _analyze_in(store, llm, "Ontario")
    assert calls == ["Ontario"]
    assert not any("all of Canada" in reason for reason in result.confidence.reasons)


def test_only_the_field_with_too_few_local_ads_uses_all_of_canada(
    store: AnalysisFakeStore, llm: FakeLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = {**STATS, "education": {"Master's degree": 1}, "experience": {"No experience": 9}}
    monkeypatch.setattr(store, "market_stats", lambda _code, region: local if region else STATS)
    result = _analyze_in(store, llm, "Yukon")
    education = next(c for c in result.categories if c.key == "education")
    experience = next(c for c in result.categories if c.key == "experience")
    assert "bachelor" in education.reason
    assert "don't require experience" in experience.reason


def test_ready_portfolio_links_count_and_failed_ones_dont(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    store.insert_document({"user_id": USER_ID, "type": "portfolio_link", "status": "ready"})
    store.insert_document({"user_id": USER_ID, "type": "portfolio_link", "status": "failed"})
    store.insert_document({"user_id": OTHER_USER_ID, "type": "portfolio_link", "status": "ready"})
    start(client, add_resume(store))
    result = store.analyses[run(store, queue)]["result"]
    portfolio = next(c for c in result["categories"] if c["key"] == "portfolio")
    assert "1 portfolio link(s)" in portfolio["reason"]


def test_a_deleted_resume_fails_cleanly(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    document_id = add_resume(store)
    start(client, document_id)
    del store.saved_extractions[document_id]
    row = store.analyses[run(store, queue)]
    assert (row["status"], row["error_code"]) == ("failed", "resume_not_found")
    assert llm.calls == 0


def test_a_missing_analysis_is_ignored(store: AnalysisFakeStore, llm: FakeLLM) -> None:
    tasks.run_analysis.apply(args=[str(uuid4()), "21232", "Developers", None])
    assert llm.calls == 0


def test_ai_outage_ends_as_failed_after_retries(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    llm.error = LLMUnavailable()
    start(client, add_resume(store))
    row = store.analyses[run(store, queue)]
    assert (row["status"], row["error_code"]) == ("failed", "ai_unavailable")
    assert row["score"] is None
    assert llm.calls == tasks.MAX_RETRIES + 1


def test_invalid_ai_output_fails_without_a_score(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm, "complete_json", lambda *_args, **_kwargs: "not json")
    start(client, add_resume(store))
    row = store.analyses[run(store, queue)]
    assert (row["status"], row["error_code"]) == ("failed", "invalid_model_output")
    assert store.judgements == {}


def test_no_market_data_at_all_fails_rather_than_scoring_zero(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = {**STATS, "education": {}, "experience": {}, "sample_size": 0, "salary_sample_size": 0}
    monkeypatch.setattr(store, "market_stats", lambda _code, _region: empty)
    monkeypatch.setattr(store, "occupation_skills", lambda _code: [])
    start(client, add_resume(store))
    args = queue.calls[-1]
    tasks.run_analysis.apply(args=[args[0], "31301", args[2], args[3]])
    row = store.analyses[args[0]]
    assert (row["status"], row["error_code"]) == ("failed", "not_enough_market_data")


def test_market_outage_is_retried_then_recorded(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    store.market_error = httpx.ConnectError("down")
    start(client, add_resume(store))
    row = store.analyses[run(store, queue)]
    assert (row["status"], row["error_code"]) == ("failed", "ai_unavailable")


def test_unexpected_errors_never_log_resume_contents(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm.error = ValueError("Jane Doe's resume says secret things")
    start(client, add_resume(store))
    row = store.analyses[run(store, queue)]
    assert row["error_code"] == "analysis_error"
    assert "secret" not in caplog.text
    assert "ValueError" in caplog.text


# --- Reading ---


def test_only_the_owner_can_read_an_analysis(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    analysis_id = start(client, add_resume(store)).json()["analysisId"]
    other = client.get(f"/analyses/{analysis_id}", headers=auth_headers(OTHER_USER_ID))
    assert other.status_code == 404
    assert client.get("/analyses", headers=auth_headers(OTHER_USER_ID)).json() == []
    mine = client.get("/analyses", headers=auth_headers())
    assert [row["id"] for row in mine.json()] == [analysis_id]


def test_reading_requires_sign_in(client: TestClient, store: AnalysisFakeStore) -> None:
    assert client.get("/analyses").status_code == 401
    assert client.get(f"/analyses/{uuid4()}").status_code == 401
