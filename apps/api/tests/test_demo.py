"""The public demo's settings: everything unlocked, payments off, a daily cap, a sample resume and
accounts that expire."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import demo, plans
from app import store as store_module
from app.config import settings
from app.routers import documents
from tests.helpers import USER_ID, FakeStore, auth_headers
from tests.test_documents_api import FakeQueue


@pytest.fixture
def demo_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_mode", True)


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> FakeQueue:
    fake = FakeQueue()
    monkeypatch.setattr(documents, "parse_document", fake)
    return fake


def test_everyone_is_pro_in_the_demo(demo_on: None) -> None:
    assert plans.entitlements(None).is_pro
    assert plans.entitlements({"plan": "free"}).analyses_limit is None


def test_outside_the_demo_a_free_account_stays_free() -> None:
    assert not plans.entitlements(None).is_pro


def test_the_plan_tells_apps_it_is_the_demo(
    client: TestClient, fake_store: FakeStore, demo_on: None
) -> None:
    body = client.get("/account/plan", headers=auth_headers()).json()
    assert body["demo"] is True
    assert body["plan"] == "pro"


def test_payments_are_off_in_the_demo(
    client: TestClient, fake_store: FakeStore, demo_on: None
) -> None:
    response = client.post(
        "/billing/checkout",
        headers=auth_headers(),
        json={"kind": "pro"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "payments_off"


def test_the_sample_resume_is_added_and_read(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue, demo_on: None
) -> None:
    response = client.post("/documents/sample", headers=auth_headers())
    assert response.status_code == 202
    body = response.json()
    assert body["fileName"] == demo.SAMPLE_RESUME_NAME
    assert queue.queued == [body["id"]]
    assert fake_store.files[f"{USER_ID}/{body['id']}.pdf"] == demo.SAMPLE_RESUME_PATH.read_bytes()


def test_the_sample_resume_only_exists_in_the_demo(client: TestClient, queue: FakeQueue) -> None:
    assert client.post("/documents/sample", headers=auth_headers()).status_code == 404


def test_the_sample_resume_needs_the_agreement(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue, demo_on: None
) -> None:
    fake_store.consent_missing.add(USER_ID)
    response = client.post("/documents/sample", headers=auth_headers())
    assert response.status_code == 403
    assert queue.queued == []


def test_uploads_stop_at_the_daily_limit_for_everyone(
    client: TestClient,
    fake_store: FakeStore,
    queue: FakeQueue,
    monkeypatch: pytest.MonkeyPatch,
    demo_on: None,
) -> None:
    monkeypatch.setattr(settings, "demo_daily_ai_jobs", 3)
    fake_store.ai_jobs_today = 3
    response = client.post("/documents/sample", headers=auth_headers())
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "demo_daily_limit"
    assert int(response.headers["retry-after"]) > 0
    assert fake_store.files == {}


def test_one_account_stops_at_its_own_daily_limit(
    client: TestClient,
    fake_store: FakeStore,
    queue: FakeQueue,
    monkeypatch: pytest.MonkeyPatch,
    demo_on: None,
) -> None:
    # One visitor can't use up the whole demo's day, even with plenty left for everyone.
    monkeypatch.setattr(settings, "demo_daily_ai_jobs", 100)
    monkeypatch.setattr(settings, "demo_user_daily_ai_jobs", 2)
    fake_store.ai_jobs_today = 2
    fake_store.ai_jobs_today_by_user[USER_ID] = 2
    response = client.post("/documents/sample", headers=auth_headers())
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "demo_user_daily_limit"
    assert fake_store.files == {}


def test_another_account_is_not_stopped_by_someone_elses_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "demo_daily_ai_jobs", 100)
    monkeypatch.setattr(settings, "demo_user_daily_ai_jobs", 2)
    store = FakeStore()
    store.ai_jobs_today = 5
    store.ai_jobs_today_by_user["someone-else"] = 5
    demo.check_daily_limit(store, USER_ID)


def test_deleting_documents_does_not_lower_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # Rows that were uploaded and deleted are gone, but the AI work they caused was recorded.
    counts = {"documents": 0, "analyses": 1, "llm_usage": 6}
    seen: list[dict[str, str]] = []

    def fake_count(table: str, params: dict[str, str]) -> int:
        seen.append({"table": table, **params})
        return counts[table]

    monkeypatch.setattr(store_module, "_count", fake_count)
    start = datetime(2026, 11, 24, tzinfo=UTC)
    assert store_module.count_ai_jobs_since(start) == 6
    assert store_module.count_ai_jobs_since(start, "user-1") == 6
    assert all(row["user_id"] == "eq.user-1" for row in seen[3:])


def test_below_the_daily_limit_nothing_is_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_daily_ai_jobs", 3)
    store = FakeStore()
    store.ai_jobs_today = 2
    demo.check_daily_limit(store, USER_ID)


def test_no_daily_limit_when_it_is_zero() -> None:
    store = FakeStore()
    store.ai_jobs_today = 10_000
    demo.check_daily_limit(store, USER_ID)


class Accounts:
    def __init__(self, ages_in_days: dict[str, int], now: datetime) -> None:
        self.accounts = [
            {"id": user, "created_at": (now - timedelta(days=age)).isoformat()}
            for user, age in ages_in_days.items()
        ]

    def accounts_created_before(self, cutoff: datetime) -> list[dict[str, Any]]:
        return [a for a in self.accounts if datetime.fromisoformat(a["created_at"]) < cutoff]


def test_old_demo_accounts_are_erased_and_new_ones_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_account_days", 30)
    now = datetime(2026, 11, 18, tzinfo=UTC)
    erased: list[str] = []
    count = demo.delete_expired_accounts(
        Accounts({"old": 31, "new": 2, "older": 90}, now), erased.append, now
    )
    assert sorted(erased) == ["old", "older"]
    assert count == 2


def test_one_failed_erase_does_not_stop_the_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "demo_account_days", 30)
    now = datetime(2026, 11, 18, tzinfo=UTC)
    erased: list[str] = []

    def erase(user_id: str) -> None:
        if user_id == "a":
            raise RuntimeError("storage down")
        erased.append(user_id)

    assert demo.delete_expired_accounts(Accounts({"a": 40, "b": 40}, now), erase, now) == 1
    assert erased == ["b"]


def test_accounts_never_expire_when_days_is_zero() -> None:
    now = datetime(2026, 11, 18, tzinfo=UTC)
    assert demo.delete_expired_accounts(Accounts({"a": 400}, now), lambda _: None, now) == 0
