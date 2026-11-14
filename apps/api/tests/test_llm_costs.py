"""AI cost tracking per person, daily budget alerts, and analytics events without resume text."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app import analytics, llm_costs
from app.config import settings
from app.llm import OllamaClient, OpenRouterClient
from tests.helpers import FakeStore

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []

    def post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        sent.append(json)
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "posthog_project_token", "phc_test")
    monkeypatch.setattr(analytics.httpx, "post", post)
    return sent


def openrouter_answering(body: dict[str, Any]) -> OpenRouterClient:
    client = OpenRouterClient("http://openrouter.test/api/v1", "test-key", "vendor/model", 5)
    client._http = httpx.Client(
        base_url="http://openrouter.test/api/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    return client


def ollama_answering(body: dict[str, Any]) -> OllamaClient:
    client = OllamaClient("http://ollama.test", "qwen3.5:4b", 5)
    client._http = httpx.Client(
        base_url="http://ollama.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    return client


OPENROUTER_ANSWER = {
    "choices": [{"message": {"content": '{"ok": true}'}}],
    "usage": {"prompt_tokens": 1000, "completion_tokens": 200, "cost": 0.0042},
}


def test_a_job_saves_one_row_per_model_with_tokens_and_cost(events: list[Any]) -> None:
    store = FakeStore()
    hosted = openrouter_answering(OPENROUTER_ANSWER)
    local = ollama_answering(
        {"message": {"content": '{"ok": true}'}, "prompt_eval_count": 300, "eval_count": 50}
    )
    with llm_costs.metering("user-1", "analysis", store):
        hosted.complete_json("system", "user", SCHEMA)
        hosted.complete_json("system", "user", SCHEMA)
        local.complete_json("system", "user", SCHEMA)

    assert store.llm_usage == [
        {
            "user_id": "user-1",
            "job": "analysis",
            "model": "vendor/model",
            "calls": 2,
            "prompt_tokens": 2000,
            "completion_tokens": 400,
            "cost_usd": "0.0084",
        },
        {
            "user_id": "user-1",
            "job": "analysis",
            "model": "qwen3.5:4b",
            "calls": 1,
            "prompt_tokens": 300,
            "completion_tokens": 50,
            "cost_usd": "0",
        },
    ]
    assert [event["event"] for event in events] == ["llm_usage", "llm_usage"]
    assert events[0]["properties"]["cost_usd"] == pytest.approx(0.0084)


def test_calls_outside_a_job_are_not_counted() -> None:
    store = FakeStore()
    openrouter_answering(OPENROUTER_ANSWER).complete_json("system", "user", SCHEMA)
    with llm_costs.metering("user-1", "extraction", store):
        pass
    assert store.llm_usage == []


def test_a_failed_save_does_not_fail_the_job() -> None:
    class Broken(FakeStore):
        def record_llm_usage(self, rows: list[dict[str, Any]]) -> None:
            raise httpx.ConnectError("down")

    with llm_costs.metering("user-1", "extraction", Broken()):
        llm_costs.record("model", 10, 5, 0.01)


def test_usage_is_saved_even_when_the_job_fails() -> None:
    store = FakeStore()
    with pytest.raises(RuntimeError), llm_costs.metering("user-1", "analysis", store):
        llm_costs.record("model", 10, 5, 0.01)
        raise RuntimeError("model gave up")
    assert store.llm_usage[0]["cost_usd"] == "0.01"


def rows(*costs: tuple[str, str]) -> list[dict[str, Any]]:
    return [{"user_id": user, "cost_usd": cost} for user, cost in costs]


def test_budgets_alert_for_the_day_and_for_each_heavy_user(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_budget_usd", 1.0)
    monkeypatch.setattr(settings, "llm_user_daily_budget_usd", 0.5)
    alerts = llm_costs.over_budget(
        rows(("a", "0.40"), ("a", "0.30"), ("b", "0.20"), ("c", "0.45")), "2026-11-14"
    )
    assert [alert.key for alert in alerts] == [
        "llm-budget:2026-11-14:total",
        "llm-budget:2026-11-14:user:a",
    ]
    assert "$1.35" in alerts[0].message


def test_spending_within_budget_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_budget_usd", 5.0)
    assert llm_costs.over_budget(rows(("a", "0.10")), "2026-11-14") == []


def test_each_alert_is_sent_once_a_day(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_daily_budget_usd", 0.0)
    monkeypatch.setattr(settings, "llm_user_daily_budget_usd", 100.0)
    store = FakeStore()
    store.record_llm_usage([{"user_id": "a", "cost_usd": "0.01"}])
    seen: set[str] = set()

    def first_time(key: str) -> bool:
        new = key not in seen
        seen.add(key)
        return new

    sent: list[str] = []
    now = datetime(2026, 11, 14, 15, tzinfo=UTC)
    llm_costs.check_budgets(store, first_time, sent.append, now)
    llm_costs.check_budgets(store, first_time, sent.append, now)
    assert len(sent) == 1


def test_analytics_events_drop_anything_that_could_be_text(events: list[Any]) -> None:
    analytics.capture(
        "user-1",
        "analysis_finished",
        {
            "status": "completed",
            "score": 70,
            "pro": False,
            "resume": "Jane Doe, 10 years of Python at Example Corp",
            "title": "senior developer",
        },
    )
    assert events[0]["properties"] == {
        "status": "completed",
        "score": 70,
        "pro": False,
        "environment": settings.environment,
    }


def test_analytics_is_off_without_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "posthog_project_token", "")
    monkeypatch.setattr(analytics.httpx, "post", lambda *a, **k: pytest.fail("sent"))
    analytics.capture("user-1", "anything")


def test_costs_add_up_exactly() -> None:
    meter = llm_costs.Meter("user-1", "analysis")
    for _ in range(10):
        meter.add("m", 0, 0, Decimal("0.1"))
    assert meter.models["m"].cost_usd == Decimal("1.0")
