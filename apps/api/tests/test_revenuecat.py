from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app import plans, revenuecat
from app.main import app
from app.routers import billing as billing_router
from tests.helpers import OTHER_USER_ID, USER_ID, FakeStore, auth_headers

NOW = datetime(2026, 11, 7, 12, tzinfo=UTC)
FUTURE = "2026-12-07T12:00:00Z"
PAST = "2026-11-01T12:00:00Z"


class FakeSource:
    def __init__(self) -> None:
        self.subscribers: dict[str, dict[str, Any]] = {}
        self.error: Exception | None = None

    def subscriber(self, app_user_id: str) -> dict[str, Any]:
        if self.error:
            raise self.error
        return self.subscribers.get(app_user_id, {})


def pro(expires: str | None = FUTURE, unsubscribed: bool = False) -> dict[str, Any]:
    return {
        "entitlements": {"pro": {"expires_date": expires, "product_identifier": "careerfit_pro_monthly"}},
        "subscriptions": {
            "careerfit_pro_monthly": {"unsubscribe_detected_at": "2026-11-07T10:00:00Z" if unsubscribed else None}
        },
    }


@pytest.fixture
def source() -> Iterator[FakeSource]:
    fake = FakeSource()
    app.dependency_overrides[billing_router.get_store_source] = lambda: fake
    yield fake
    app.dependency_overrides.pop(billing_router.get_store_source, None)


# --- Pro from the stores ---


def test_an_active_store_entitlement_makes_the_account_pro() -> None:
    store, source = FakeStore(), FakeSource()
    source.subscribers[USER_ID] = pro()
    revenuecat.sync_pro(USER_ID, store, source, NOW)
    row = store.get_subscription(USER_ID)
    assert row is not None
    assert (row["plan"], row["provider"], row["current_period_end"]) == ("pro", "revenuecat", FUTURE)
    assert row["cancel_at_period_end"] is False
    assert plans.entitlements(row, NOW).is_pro


def test_turning_off_renewal_in_the_store_keeps_pro_until_the_end() -> None:
    store, source = FakeStore(), FakeSource()
    source.subscribers[USER_ID] = pro(unsubscribed=True)
    revenuecat.sync_pro(USER_ID, store, source, NOW)
    row = store.get_subscription(USER_ID)
    assert row is not None
    assert row["plan"] == "pro"
    assert row["cancel_at_period_end"] is True


def test_an_expired_store_plan_returns_the_account_to_free() -> None:
    store, source = FakeStore(), FakeSource()
    source.subscribers[USER_ID] = pro()
    revenuecat.sync_pro(USER_ID, store, source, NOW)
    source.subscribers[USER_ID] = pro(expires=PAST)
    revenuecat.sync_pro(USER_ID, store, source, NOW)
    row = store.get_subscription(USER_ID)
    assert row is not None
    assert row["plan"] == "free"


def test_a_store_plan_ends_on_its_date_even_without_a_new_check() -> None:
    row = {"plan": "pro", "status": "active", "provider": "revenuecat", "current_period_end": PAST}
    assert not plans.entitlements(row, NOW).is_pro
    row["current_period_end"] = FUTURE
    assert plans.entitlements(row, NOW).is_pro


def test_a_store_check_never_changes_a_stripe_plan() -> None:
    store, source = FakeStore(), FakeSource()
    store.update_subscription(USER_ID, {"plan": "pro", "status": "active", "provider": "stripe"})
    revenuecat.sync_pro(USER_ID, store, source, NOW)  # no store entitlement at all
    row = store.get_subscription(USER_ID)
    assert row is not None
    assert (row["plan"], row["provider"]) == ("pro", "stripe")


def test_no_store_purchase_leaves_a_free_account_alone() -> None:
    store, source = FakeStore(), FakeSource()
    revenuecat.sync_pro(USER_ID, store, source, NOW)
    row = store.get_subscription(USER_ID)
    assert row is not None
    assert (row["plan"], row["provider"]) == ("free", None)


def test_the_sync_endpoint_updates_the_plan(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    source.subscribers[USER_ID] = pro()
    assert client.post("/billing/app-store/sync", headers=auth_headers()).status_code == 204
    assert client.get("/account/plan", headers=auth_headers()).json()["plan"] == "pro"


def test_the_sync_endpoint_needs_store_keys(client: TestClient, fake_store: FakeStore) -> None:
    response = client.post("/billing/app-store/sync", headers=auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "billing_unavailable"


def test_a_store_outage_is_reported(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    source.error = revenuecat.RevenueCatUnavailable()
    assert client.post("/billing/app-store/sync", headers=auth_headers()).status_code == 503


# --- Reports bought in the app ---


ANALYSIS = "44444444-4444-4444-4444-444444444444"
SECOND = "55555555-5555-5555-5555-555555555555"


def with_analyses(store: FakeStore, owner: str = USER_ID) -> None:
    rows = {aid: {"id": aid, "user_id": owner, "status": "completed"} for aid in (ANALYSIS, SECOND)}
    store.get_analysis = lambda aid, uid=None: (  # type: ignore[method-assign]
        dict(rows[aid]) if aid in rows and (uid is None or rows[aid]["user_id"] == uid) else None
    )


def report_purchase(transaction: str = "txn_1") -> dict[str, Any]:
    return {"non_subscriptions": {"careerfit_detailed_report": [{"id": transaction, "store_transaction_id": f"store_{transaction}"}]}}


def claim(client: TestClient, analysis_id: str = ANALYSIS, transaction: str = "txn_1") -> Any:
    return client.post(
        "/billing/app-store/report",
        json={"analysisId": analysis_id, "transactionId": transaction},
        headers=auth_headers(),
    )


def test_a_confirmed_store_purchase_unlocks_the_report(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    with_analyses(fake_store)
    source.subscribers[USER_ID] = report_purchase()
    assert claim(client).status_code == 204
    assert fake_store.purchased_report_ids(USER_ID) == {ANALYSIS}
    assert fake_store.report_purchases[ANALYSIS]["provider"] == "revenuecat"


def test_the_store_transaction_id_is_accepted_too(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    with_analyses(fake_store)
    source.subscribers[USER_ID] = report_purchase()
    assert claim(client, transaction="store_txn_1").status_code == 204


def test_an_unknown_purchase_unlocks_nothing(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    with_analyses(fake_store)
    source.subscribers[USER_ID] = report_purchase()
    response = claim(client, transaction="made_up")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "purchase_not_found"
    assert fake_store.purchased_report_ids(USER_ID) == set()


def test_one_purchase_unlocks_one_result_only(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    with_analyses(fake_store)
    source.subscribers[USER_ID] = report_purchase()
    assert claim(client, ANALYSIS).status_code == 204
    assert claim(client, SECOND).status_code == 409
    assert fake_store.purchased_report_ids(USER_ID) == {ANALYSIS}


def test_someone_elses_result_cant_be_unlocked(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    with_analyses(fake_store, owner=OTHER_USER_ID)
    source.subscribers[USER_ID] = report_purchase()
    assert claim(client).status_code == 404


def test_claiming_an_already_unlocked_report_changes_nothing(
    client: TestClient, fake_store: FakeStore, source: FakeSource
) -> None:
    with_analyses(fake_store)
    fake_store.record_report_purchase(USER_ID, ANALYSIS, "stripe", "cs_1")
    source.error = AssertionError("the store isn't asked")
    assert claim(client).status_code == 204


# --- The HTTP client ---


def test_the_client_asks_revenuecat_about_this_account_only() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"subscriber": {"entitlements": {}}})

    client = revenuecat.RevenueCatClient("sk_test", httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.subscriber("user/with odd chars") == {"entitlements": {}}
    # Encoded, so an id can't step into another path on RevenueCat's side.
    assert seen[0].url.raw_path == b"/v1/subscribers/user%2Fwith%20odd%20chars"
    assert seen[0].headers["authorization"] == "Bearer sk_test"


def test_the_client_reports_an_outage() -> None:
    client = revenuecat.RevenueCatClient(
        "sk_test", httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    )
    with pytest.raises(revenuecat.RevenueCatUnavailable):
        client.subscriber(USER_ID)


def test_the_client_needs_a_key() -> None:
    with pytest.raises(revenuecat.RevenueCatUnavailable):
        revenuecat.RevenueCatClient("")
