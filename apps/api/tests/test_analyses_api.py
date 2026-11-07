import json
import re
from copy import deepcopy
from datetime import UTC, date, datetime
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


ACTION_ANSWER = {
    "gap": 1,
    "type": "course",
    "title": "Debugging basics",
    "details": "Practise finding faults in small programs.",
    "expected_result": "You can debug your own code.",
    "providers": ["Coursera"],
    "weeks": 3,
    "unsure": False,
}
RESUME_LINE = "Patient assessment, wound care and triage in the emergency department."
TAILOR_LINE = "Fixed bugs in Python services for the billing team every week"
# Skill 2 of those the analysis found ("computer programming", "debug software").
TAILORED_ANSWER = {
    "line": 1,
    "skill": 2,
    "after": "Debugged and fixed bugs in Python services for the billing team every week",
}
REWRITE_ANSWER = {
    "line": 1,
    "after": "Assessed patients, provided wound care, and performed triage in the emergency department.",
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
        properties = schema["properties"]
        if "tailor lines" in system:
            return json.dumps({"rewrites": [TAILORED_ANSWER]})
        if "judgements" in properties:
            return json.dumps(SKILLS_ANSWER)
        if "actions" in properties:
            return json.dumps({"actions": [ACTION_ANSWER]})
        if "rewrites" in properties:
            return json.dumps({"rewrites": [REWRITE_ANSWER]})
        if "translations" in properties:
            terms = re.findall(r"^(\d+)\. (.+)$", user, re.MULTILINE)
            return json.dumps(
                {"translations": [{"number": int(n), "text": f"перевод {term}"} for n, term in terms]}
            )
        return json.dumps(RELEVANCE_ANSWER)


class AnalysisFakeStore(FakeStore):
    def __init__(self) -> None:
        super().__init__()
        self.analyses: dict[str, dict[str, Any]] = {}
        self.judgements: dict[tuple[str, str], dict[str, Any]] = {}
        self.target_roles: list[dict[str, str]] = []
        self.market_error: Exception | None = None
        self.translations: dict[str, str] = {}
        self.tailored: dict[str, dict[str, Any]] = {}
        # Most tests start several analyses, so their account is Pro. The limit tests switch it to free.
        self.update_subscription(USER_ID, {"plan": "pro", "status": "active"})

    def count_analyses_since(self, user_id: str, start: Any) -> int:
        return sum(
            1
            for row in self.analyses.values()
            if row["user_id"] == user_id and row["status"] != "failed" and row["created_at"] >= start.isoformat()
        )

    def start_analysis_within_limit(
        self, user_id: str, target_role_id: str, document_id: str, limit: int | None, period_start: Any
    ) -> dict[str, Any] | None:
        if limit is not None and self.count_analyses_since(user_id, period_start) >= limit:
            return None
        return self.insert_analysis(
            {
                "user_id": user_id,
                "target_role_id": target_role_id,
                "document_id": document_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )

    def match_occupation(self, _embedding: list[float]) -> dict[str, Any] | None:
        return MATCH

    def get_occupation(self, code: str) -> dict[str, Any] | None:
        names = {"31301": "Registered nurses"}
        if code not in names:
            return None
        return {"occupation_code": code, "occupation_name": names[code]}

    def match_occupations(self, _embedding: list[float], _count: int) -> list[dict[str, Any]]:
        return [{"occupation_code": "21231", "occupation_name": "Software engineers", "similarity": 0.9}]

    def market_stats(self, _code: str, _region: str | None) -> dict[str, Any]:
        if self.market_error:
            raise self.market_error
        return STATS

    def occupation_skills(self, code: str) -> list[dict[str, Any]]:
        if code == "21231":
            return [
                {"required": True, "rank": n, "skills": {"name": f"skill {n}", "esco_id": str(n)}}
                for n in range(6)
            ]
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

    def get_tailored_rewrites(self, analysis_id: str, user_id: str) -> list[dict[str, Any]] | None:
        saved = self.tailored.get(analysis_id)
        return list(saved["rewrites"]) if saved and saved["user_id"] == user_id else None

    def save_tailored_rewrites(
        self,
        analysis_id: str,
        user_id: str,
        rewrites: list[dict[str, Any]],
        model: str,
        prompt_version: str,
    ) -> None:
        self.tailored[analysis_id] = {"user_id": user_id, "rewrites": json.loads(json.dumps(rewrites))}

    def get_translations(self, terms: list[str], _language: str) -> dict[str, str]:
        return {term: self.translations[term] for term in terms if term in self.translations}

    def save_translations(self, translations: dict[str, str], _language: str) -> None:
        self.translations.update(translations)


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[list[Any]] = []
        self.error: Exception | None = None

    def apply_async(self, args: list[Any], retry: bool = True) -> None:
        if self.error:
            raise self.error
        self.calls.append(args)

    def apply(self, args: list[Any]) -> None:
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
    # The tailoring endpoint asks for the model itself; tests must never reach the real one.
    monkeypatch.setattr(analyses, "get_llm", lambda: fake)
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
    assert queue.calls == [[analysis_id, "21232", MATCH["occupation_name"], "Ontario", "en"]]
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


# --- Plan limits ---


def test_a_free_account_gets_one_analysis_a_month(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    store.update_subscription(USER_ID, {"plan": "free"})
    resume = add_resume(store)
    assert start(client, resume).status_code == 202
    response = start(client, resume)
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "limit_reached"
    assert len(queue.calls) == 1
    assert len(store.analyses) == 1


def test_a_failed_analysis_doesnt_use_up_the_free_one(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    store.update_subscription(USER_ID, {"plan": "free"})
    resume = add_resume(store)
    start(client, resume)
    next(iter(store.analyses.values()))["status"] = "failed"
    assert start(client, resume).status_code == 202


def test_last_months_analyses_dont_count(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    store.update_subscription(USER_ID, {"plan": "free"})
    resume = add_resume(store)
    start(client, resume)
    next(iter(store.analyses.values()))["created_at"] = "2000-01-31T23:59:59+00:00"
    assert start(client, resume).status_code == 202


def test_pro_has_no_monthly_limit(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    resume = add_resume(store)
    assert [start(client, resume).status_code for _ in range(3)] == [202, 202, 202]


def test_a_cancelled_pro_plan_is_limited_again(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    store.update_subscription(USER_ID, {"plan": "pro", "status": "canceled"})
    resume = add_resume(store)
    assert start(client, resume).status_code == 202
    assert start(client, resume).status_code == 402


def test_the_database_has_the_last_word_on_the_limit(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Two requests at once both pass the quick check; the locked database step lets only one through.
    store.update_subscription(USER_ID, {"plan": "free"})
    monkeypatch.setattr(store, "count_analyses_since", lambda user_id, start: 0)
    monkeypatch.setattr(store, "start_analysis_within_limit", lambda *args: None)
    response = start(client, add_resume(store))
    assert response.status_code == 402
    assert queue.calls == []


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
    # Each run asks about actions, but the saved skill answers for both jobs are reused.
    questions_about_skills_and_fit = 4
    actions_and_two_runs = 2
    assert llm.calls == questions_about_skills_and_fit + actions_and_two_runs
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
    assert "Portfolio links you added: 1." in portfolio["reason"]


def test_the_full_report_is_saved_with_the_score(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    start(client, add_resume(store, parsed_text=RESUME_LINE))
    analysis_id = run(store, queue)
    body = client.get(f"/analyses/{analysis_id}", headers=auth_headers()).json()
    assert body["status"] == "completed"
    report = body["result"]["report"]
    assert body["result"]["reportError"] is None
    assert report["gaps"]
    assert report["actions"][0]["title"] == "Debugging basics"
    assert report["rewrites"] == [{"before": RESUME_LINE, "after": REWRITE_ANSWER["after"]}]
    assert report["alternativeRoles"][0]["occupationName"] == "Software engineers"
    assert report["plan"]["thirtyDays"]
    assert report["notes"]
    assert "not a guarantee" in body["result"]["disclaimer"]
    # History and progress need these saved on the analysis itself.
    assert store.analyses[analysis_id]["result"]["report"]["plan"]
    assert store.analyses[analysis_id]["score"] == body["score"]


def test_the_score_is_saved_before_recommendations_begin(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[dict[str, Any]] = []

    def watch(**_kwargs: Any) -> Any:
        row = next(iter(store.analyses.values()))
        seen.append({"status": row["status"], "score": row["score"], "result": row["result"]})
        raise ValueError("stop here")

    monkeypatch.setattr(tasks, "build_report", watch)
    start(client, add_resume(store))
    run(store, queue)
    assert seen[0]["status"] == "processing"
    assert seen[0]["score"] is not None
    assert seen[0]["result"]["score"] == seen[0]["score"]


def test_the_page_can_show_the_score_while_the_report_is_being_made(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = start(client, add_resume(store)).json()["analysisId"]
    run(store, queue)
    row = store.analyses[analysis_id]
    partial = {key: value for key, value in row["result"].items() if key not in ("report", "report_error")}
    store.update_analysis(analysis_id, {"status": "processing", "result": partial, "completed_at": None})
    body = client.get(f"/analyses/{analysis_id}", headers=auth_headers()).json()
    assert body["status"] == "processing"
    assert body["result"]["score"] == body["score"]
    assert body["result"]["report"] is None


def test_a_recommendation_failure_keeps_the_score(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(**_kwargs: Any) -> Any:
        raise ValueError("Jane Doe's resume says secret things")

    monkeypatch.setattr(tasks, "build_report", broken)
    start(client, add_resume(store))
    row = store.analyses[run(store, queue)]
    assert row["status"] == "completed"
    assert row["score"] is not None
    assert row["result"]["report"] is None
    assert row["result"]["report_error"] == "analysis_error"


def test_an_ai_outage_during_recommendations_keeps_the_score(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def down(**_kwargs: Any) -> Any:
        calls.append(1)
        raise LLMUnavailable()

    monkeypatch.setattr(tasks, "build_report", down)
    start(client, add_resume(store))
    row = store.analyses[run(store, queue)]
    assert len(calls) == tasks.MAX_RETRIES + 1
    assert row["status"] == "completed"
    assert row["score"] is not None
    assert row["result"]["report_error"] == "ai_unavailable"


def test_picking_a_suggestion_skips_guessing_the_occupation(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_guessing(_embedding: list[float]) -> None:
        raise AssertionError("should not search")

    monkeypatch.setattr(store, "match_occupation", no_guessing)
    response = start(client, add_resume(store), role="медсестра", occupationCode="31301", language="ru")
    assert response.status_code == 202
    assert queue.calls[0][1:] == ["31301", "Registered nurses", "Ontario", "ru"]


def test_an_unknown_occupation_code_is_refused(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    response = start(client, add_resume(store), occupationCode="99999")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "role_not_found"
    assert queue.calls == []


def test_an_unsupported_language_is_refused(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    assert start(client, add_resume(store), language="de").status_code == 422


def test_without_a_queue_the_job_runs_after_the_response(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue
) -> None:
    from app.celery_app import celery_app

    # Restored by the conftest fixture. Monkeypatching this setting breaks at teardown.
    celery_app.conf.task_always_eager = True
    queue.error = OperationalError("the queue must not be used")
    response = start(client, add_resume(store))
    assert response.status_code == 202
    assert len(queue.calls) == 1


def test_progress_stages_are_recorded(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stages: list[str | None] = []
    original = store.update_analysis

    def spy(analysis_id: str, fields: dict[str, Any]) -> None:
        if "stage" in fields:
            stages.append(fields["stage"])
        original(analysis_id, fields)

    monkeypatch.setattr(store, "update_analysis", spy)
    start(client, add_resume(store))
    run(store, queue)
    assert stages == ["matching", "planning", "alternatives", None]


def test_a_russian_analysis_is_saved_in_russian_with_the_same_score(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    document_id = add_resume(store)
    start(client, document_id)
    english = store.analyses[run(store, queue)]
    start(client, document_id, language="ru")
    russian = store.analyses[run(store, queue)]
    assert russian["score"] == english["score"]
    result = russian["result"]
    assert result["required_skills"][0]["name"] == "перевод computer programming"
    assert result["required_skills"][0]["evidence"] == ["Навык: Python"]
    assert result["occupation_name"].startswith("перевод")
    assert re.search("[А-Яа-я]", result["categories"][0]["reason"])
    assert result["report"]["alternative_roles"][0]["occupation_name"] == "перевод Software engineers"
    assert re.search("[А-Яа-я]", result["report"]["alternative_roles"][0]["reason"])
    assert re.search("[А-Яа-я]", result["disclaimer"])


def test_translations_are_saved_for_next_time(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    document_id = add_resume(store)
    start(client, document_id, language="ru")
    run(store, queue)
    assert store.translations["computer programming"] == "перевод computer programming"
    calls = llm.calls
    start(client, document_id, language="ru")
    run(store, queue)
    # Only the suggested actions are asked for again.
    assert llm.calls == calls + 1


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


# --- Telling the phone ---


def test_a_finished_analysis_alerts_the_persons_phones(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks.push, "send_report_ready", lambda user_id, analysis_id, **_: sent.append((user_id, analysis_id))
    )
    start(client, add_resume(store))
    analysis_id = run(store, queue)
    assert store.analyses[analysis_id]["status"] == "completed"
    assert sent == [(USER_ID, analysis_id)]


def test_a_score_without_its_plan_still_alerts(
    client: TestClient,
    store: AnalysisFakeStore,
    queue: FakeQueue,
    llm: FakeLLM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(tasks.push, "send_report_ready", lambda _user, analysis_id, **_: sent.append(analysis_id))
    # Any real score will do, so one is taken from a normal run.
    start(client, add_resume(store))
    finished = store.analyses[run(store, queue)]
    scored = tasks.ScoreResult.model_validate(finished["result"])
    sent.clear()
    store.analyses["partial"] = {"user_id": USER_ID}
    tasks._end_analysis_early("partial", USER_ID, scored, tasks.datetime.now(tasks.UTC), "timeout")
    assert store.analyses["partial"]["status"] == "completed"
    assert sent == ["partial"]


def test_a_failed_analysis_sends_no_alert(
    store: AnalysisFakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(tasks.push, "send_report_ready", lambda _user, analysis_id, **_: sent.append(analysis_id))
    store.analyses["failed"] = {"user_id": USER_ID}
    tasks._end_analysis_early("failed", USER_ID, None, tasks.datetime.now(tasks.UTC), "timeout")
    assert store.analyses["failed"]["status"] == "failed"
    assert sent == []


# --- Pro: progress over time ---


def finished(client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, **changes: Any) -> str:
    start(client, add_resume(store, parsed_text=TAILOR_LINE), **changes)
    return run(store, queue)


def test_progress_is_part_of_pro(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    store.update_subscription(USER_ID, {"plan": "free"})
    response = client.get("/analyses/progress", headers=auth_headers())
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "pro_required"


def test_progress_follows_one_job_over_time(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    first = finished(client, store, queue)
    second = finished(client, store, queue)
    store.analyses[first]["created_at"] = "2026-10-01T00:00:00+00:00"
    store.analyses[first]["score"] = store.analyses[second]["score"] - 7
    # An unfinished analysis isn't a point on the line.
    start(client, add_resume(store))
    tracks = client.get("/analyses/progress", headers=auth_headers()).json()
    assert len(tracks) == 1
    track = tracks[0]
    assert (track["role"], track["region"]) == ("software developer", "Ontario")
    assert [point["analysisId"] for point in track["points"]] == [first, second]
    assert track["change"] == 7


# --- Pro: the resume tailored to one job ---


def test_tailoring_a_resume_is_part_of_pro(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    store.update_subscription(USER_ID, {"plan": "free"})
    calls = llm.calls
    response = client.post(f"/analyses/{analysis_id}/tailored-rewrites", headers=auth_headers())
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "pro_required"
    assert llm.calls == calls


def test_tailored_lines_are_made_once_and_kept(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    url = f"/analyses/{analysis_id}/tailored-rewrites"
    assert client.get(url, headers=auth_headers()).status_code == 404
    calls = llm.calls
    body = client.post(url, headers=auth_headers()).json()
    assert body["job"] == "software developer"
    assert body["rewrites"] == [
        {"before": TAILOR_LINE, "after": TAILORED_ANSWER["after"], "skill": "debug software"}
    ]
    assert llm.calls == calls + 1
    # Asking again, or after Pro ends, shows the saved lines without the AI.
    assert client.post(url, headers=auth_headers()).json() == body
    store.update_subscription(USER_ID, {"plan": "free"})
    assert client.get(url, headers=auth_headers()).json() == body
    assert llm.calls == calls + 1


def test_tailoring_when_the_ai_is_down(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    llm.error = LLMUnavailable("down")
    response = client.post(f"/analyses/{analysis_id}/tailored-rewrites", headers=auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ai_unavailable"
    assert store.tailored == {}


def test_someone_elses_result_cant_be_tailored(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    response = client.post(
        f"/analyses/{analysis_id}/tailored-rewrites", headers=auth_headers(OTHER_USER_ID)
    )
    assert response.status_code == 404


# --- The detailed report ---


def pdf_text(content: bytes) -> str:
    import io

    import pdfplumber

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def test_the_detailed_report_needs_buying_first(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    response = client.get(f"/analyses/{analysis_id}/report.pdf", headers=auth_headers())
    assert response.status_code == 402
    assert response.json()["detail"]["code"] == "report_not_purchased"


def test_a_bought_report_downloads_as_a_pdf(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    store.record_report_purchase(USER_ID, analysis_id, "stripe", "cs_1")
    response = client.get(f"/analyses/{analysis_id}/report.pdf", headers=auth_headers())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith('attachment; filename="careerfit-report-')
    text = pdf_text(response.content)
    score = store.analyses[analysis_id]["score"]
    assert f"Match score: {round(score)} out of 100" in text
    assert "software developer · Ontario" in text
    assert "Your 30, 60 and 90 day plan" in text


def test_the_report_can_be_in_russian(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue, language="ru")
    store.record_report_purchase(USER_ID, analysis_id, "stripe", "cs_1")
    response = client.get(
        f"/analyses/{analysis_id}/report.pdf", params={"language": "ru"}, headers=auth_headers()
    )
    text = pdf_text(response.content)
    assert "Оценка совпадения" in text
    assert "Онтарио" in text


def test_a_report_bought_by_someone_else_isnt_yours(
    client: TestClient, store: AnalysisFakeStore, queue: FakeQueue, llm: FakeLLM
) -> None:
    analysis_id = finished(client, store, queue)
    store.record_report_purchase(OTHER_USER_ID, analysis_id, "stripe", "cs_1")
    response = client.get(f"/analyses/{analysis_id}/report.pdf", headers=auth_headers())
    assert response.status_code == 402
