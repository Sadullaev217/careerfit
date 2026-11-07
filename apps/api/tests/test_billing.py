import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
import stripe
from fastapi.testclient import TestClient

from app import billing, plans
from app.main import app
from app.routers import account
from app.routers import billing as billing_router
from tests.helpers import OTHER_USER_ID, USER_ID, FakeStore, auth_headers

PERIOD_END = 1_800_000_000  # 2027-01-15


class FakeGateway:
    def __init__(self) -> None:
        self.customers: list[tuple[str, str | None]] = []
        self.checkouts: list[dict[str, Any]] = []
        self.portals: list[tuple[str, str]] = []
        self.subscriptions: dict[str, dict[str, Any]] = {}
        self.subscription_reads = 0
        self.deleted_customers: list[str] = []
        self.delete_error: Exception | None = None
        self.read_error: Exception | None = None

    def create_customer(self, user_id: str, email: str | None) -> str:
        self.customers.append((user_id, email))
        return f"cus_{len(self.customers)}"

    def price_id(self, lookup_key: str) -> str:
        return f"price_for_{lookup_key}"

    def create_checkout(self, params: dict[str, Any]) -> str:
        self.checkouts.append(params)
        return f"https://checkout.stripe.test/{len(self.checkouts)}"

    def create_portal(self, customer_id: str, return_url: str) -> str:
        self.portals.append((customer_id, return_url))
        return "https://billing.stripe.test/session"

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        self.subscription_reads += 1
        if self.read_error:
            raise self.read_error
        return self.subscriptions[subscription_id]

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if signature != "good-signature":
            raise billing.InvalidEvent
        event: dict[str, Any] = json.loads(payload)
        return event

    def delete_customer(self, customer_id: str) -> None:
        if self.delete_error:
            raise self.delete_error
        self.deleted_customers.append(customer_id)


@pytest.fixture
def gateway(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGateway]:
    fake = FakeGateway()
    app.dependency_overrides[billing_router.get_gateway] = lambda: fake
    monkeypatch.setattr(account, "gateway_factory", lambda: fake)
    yield fake
    app.dependency_overrides.pop(billing_router.get_gateway, None)


def subscription(
    subscription_id: str = "sub_1",
    status: str = "active",
    user_id: str = USER_ID,
    customer: str = "cus_1",
    cancel_at_period_end: bool = False,
) -> dict[str, Any]:
    return {
        "id": subscription_id,
        "customer": customer,
        "status": status,
        "cancel_at_period_end": cancel_at_period_end,
        "metadata": {"user_id": user_id},
        "items": {"data": [{"current_period_end": PERIOD_END}]},
    }


def event(event_type: str, obj: dict[str, Any], event_id: str = "evt_1") -> dict[str, Any]:
    return {"id": event_id, "type": event_type, "data": {"object": obj}}


def send(client: TestClient, payload: dict[str, Any], signature: str = "good-signature") -> Any:
    return client.post(
        "/billing/stripe-webhook",
        content=json.dumps(payload),
        headers={"Stripe-Signature": signature, "Content-Type": "application/json"},
    )


def completed_analysis(store: FakeStore, user_id: str = USER_ID, status: str = "completed") -> str:
    # The billing routes only read analyses, so a plain dict store is enough here.
    analysis_id = "33333333-3333-3333-3333-333333333333"
    analyses = getattr(store, "analyses", {})
    analyses[analysis_id] = {
        "id": analysis_id,
        "user_id": user_id,
        "status": status,
        "result": {"score": 60} if status == "completed" else None,
    }
    store.analyses = analyses  # type: ignore[attr-defined]
    store.get_analysis = lambda aid, uid=None: (  # type: ignore[method-assign]
        dict(analyses[aid]) if aid in analyses and (uid is None or analyses[aid]["user_id"] == uid) else None
    )
    return analysis_id


# --- Plan rules ---


@pytest.mark.parametrize(
    ("row", "plan", "limit"),
    [
        (None, "free", 1),
        ({"plan": "free", "status": "active"}, "free", 1),
        ({"plan": "pro", "status": "active"}, "pro", None),
        ({"plan": "pro", "status": "trialing"}, "pro", None),
        # Stripe is retrying a failed payment: access continues until it gives up.
        ({"plan": "pro", "status": "past_due"}, "pro", None),
        ({"plan": "pro", "status": "canceled"}, "free", 1),
        ({"plan": "pro", "status": "unpaid"}, "free", 1),
        ({"plan": "pro", "status": "incomplete"}, "free", 1),
    ],
)
def test_plan_follows_the_subscription_status(
    row: dict[str, Any] | None, plan: str, limit: int | None
) -> None:
    result = plans.entitlements(row)
    assert result.plan == plan
    assert result.analyses_limit == limit


def test_the_monthly_limit_resets_on_the_first_of_the_month_in_utc() -> None:
    late_december = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)
    assert plans.month_start(late_december) == datetime(2026, 12, 1, tzinfo=UTC)
    assert plans.next_month_start(late_december) == datetime(2027, 1, 1, tzinfo=UTC)
    assert plans.next_month_start(datetime(2026, 11, 7, tzinfo=UTC)) == datetime(2026, 12, 1, tzinfo=UTC)


# --- Plan endpoint ---


def test_a_free_account_sees_its_limit_and_usage(client: TestClient, fake_store: FakeStore) -> None:
    fake_store.count_analyses_since = lambda user_id, start: 1  # type: ignore[method-assign]
    body = client.get("/account/plan", headers=auth_headers()).json()
    assert body["plan"] == "free"
    assert body["analysesUsed"] == 1
    assert body["analysesLimit"] == 1
    assert body["limitResetsAt"] == plans.next_month_start(datetime.now(UTC)).date().isoformat()
    assert body["purchasedReports"] == []


def test_a_pro_account_has_no_limit_and_shows_renewal(client: TestClient, fake_store: FakeStore) -> None:
    fake_store.update_subscription(
        USER_ID,
        {
            "plan": "pro",
            "status": "active",
            "provider": "stripe",
            "current_period_end": "2027-01-15T00:00:00+00:00",
            "cancel_at_period_end": True,
        },
    )
    body = client.get("/account/plan", headers=auth_headers()).json()
    assert body["plan"] == "pro"
    assert body["analysesLimit"] is None
    assert body["cancelAtPeriodEnd"] is True
    assert body["currentPeriodEnd"] == "2027-01-15T00:00:00+00:00"
    assert body["provider"] == "stripe"


def test_purchased_reports_are_listed(client: TestClient, fake_store: FakeStore) -> None:
    fake_store.record_report_purchase(USER_ID, "a1", "stripe", "cs_1")
    fake_store.record_report_purchase(OTHER_USER_ID, "b1", "stripe", "cs_2")
    body = client.get("/account/plan", headers=auth_headers()).json()
    assert body["purchasedReports"] == ["a1"]


# --- Checkout and portal ---


def test_pro_checkout_returns_a_stripe_link(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    response = client.post(
        "/billing/checkout", json={"kind": "pro", "language": "ru"}, headers=auth_headers()
    )
    assert response.status_code == 200
    assert response.json()["url"].startswith("https://checkout.stripe.test/")
    params = gateway.checkouts[0]
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_for_careerfit_pro_monthly", "quantity": 1}]
    assert params["client_reference_id"] == USER_ID
    assert params["subscription_data"]["metadata"]["user_id"] == USER_ID
    assert params["locale"] == "ru"
    assert params["success_url"].endswith("/ru/settings?checkout=pro")
    # The Stripe customer is remembered, so a second checkout doesn't create another one.
    assert fake_store.get_subscription(USER_ID)["stripe_customer_id"] == "cus_1"  # type: ignore[index]
    client.post("/billing/checkout", json={"kind": "pro"}, headers=auth_headers())
    assert len(gateway.customers) == 1
    assert gateway.customers[0] == (USER_ID, "a@example.com")


def test_a_pro_account_cant_buy_pro_again(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    fake_store.update_subscription(USER_ID, {"plan": "pro", "status": "active"})
    response = client.post("/billing/checkout", json={"kind": "pro"}, headers=auth_headers())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_pro"
    assert gateway.checkouts == []


def test_checkout_needs_sign_in(client: TestClient, gateway: FakeGateway) -> None:
    assert client.post("/billing/checkout", json={"kind": "pro"}).status_code == 401


def test_report_checkout_is_for_one_finished_result(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    analysis_id = completed_analysis(fake_store)
    response = client.post(
        "/billing/checkout", json={"kind": "report", "analysisId": analysis_id}, headers=auth_headers()
    )
    assert response.status_code == 200
    params = gateway.checkouts[0]
    assert params["mode"] == "payment"
    assert params["line_items"][0]["price"] == "price_for_careerfit_detailed_report"
    assert params["metadata"] == {"user_id": USER_ID, "kind": "report", "analysis_id": analysis_id}
    assert params["success_url"].endswith(f"/en/analyses/{analysis_id}?checkout=report")


@pytest.mark.parametrize(
    ("owner", "status", "already_bought", "code"),
    [
        (OTHER_USER_ID, "completed", False, "not_found"),
        (USER_ID, "processing", False, "analysis_not_finished"),
        (USER_ID, "completed", True, "already_purchased"),
    ],
)
def test_report_checkout_is_refused_when_it_cant_be_bought(
    client: TestClient,
    fake_store: FakeStore,
    gateway: FakeGateway,
    owner: str,
    status: str,
    already_bought: bool,
    code: str,
) -> None:
    analysis_id = completed_analysis(fake_store, owner, status)
    if already_bought:
        fake_store.record_report_purchase(USER_ID, analysis_id, "stripe", "cs_old")
    response = client.post(
        "/billing/checkout", json={"kind": "report", "analysisId": analysis_id}, headers=auth_headers()
    )
    assert response.json()["detail"]["code"] == code
    assert gateway.checkouts == []


def test_report_checkout_needs_a_result(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    response = client.post("/billing/checkout", json={"kind": "report"}, headers=auth_headers())
    assert response.json()["detail"]["code"] == "analysis_required"


def test_payments_are_unavailable_without_stripe_keys(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(billing.settings, "stripe_secret_key", "")
    response = client.post("/billing/checkout", json={"kind": "pro"}, headers=auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "billing_unavailable"


def test_a_stripe_error_is_reported_as_payments_unavailable(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(params: dict[str, Any]) -> str:
        raise stripe.AuthenticationError("Invalid API Key provided")

    monkeypatch.setattr(gateway, "create_checkout", refuse)
    response = client.post("/billing/checkout", json={"kind": "pro"}, headers=auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "billing_unavailable"


def test_the_portal_needs_an_earlier_payment(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    response = client.post("/billing/portal", json={}, headers=auth_headers())
    assert response.status_code == 404
    fake_store.update_subscription(USER_ID, {"stripe_customer_id": "cus_9"})
    response = client.post("/billing/portal", json={"language": "ru"}, headers=auth_headers())
    assert response.json()["url"] == "https://billing.stripe.test/session"
    assert gateway.portals == [("cus_9", "http://localhost:3000/ru/settings")]


# --- Webhooks ---


def test_an_unsigned_event_is_rejected_and_changes_nothing(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription()
    response = send(client, event("customer.subscription.created", {"id": "sub_1"}), "forged")
    assert response.status_code == 400
    assert fake_store.get_subscription(USER_ID)["plan"] == "free"  # type: ignore[index]
    assert fake_store.stripe_events == {}


def test_a_new_subscription_upgrades_the_account(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription()
    assert send(client, event("customer.subscription.created", {"id": "sub_1"})).status_code == 200
    row = fake_store.get_subscription(USER_ID)
    assert row is not None
    assert row["plan"] == "pro"
    assert row["status"] == "active"
    assert row["provider"] == "stripe"
    assert row["stripe_subscription_id"] == "sub_1"
    assert row["stripe_customer_id"] == "cus_1"
    assert row["current_period_end"] == "2027-01-15T08:00:00+00:00"


def test_the_same_event_twice_is_handled_once(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription()
    payload = event("customer.subscription.created", {"id": "sub_1"})
    send(client, payload)
    send(client, payload)
    assert gateway.subscription_reads == 1
    assert fake_store.stripe_events == {"evt_1": "customer.subscription.created"}


def test_events_use_stripes_current_subscription_not_the_events_copy(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    # The "created" event arrives late, after the subscription was already cancelled.
    gateway.subscriptions["sub_1"] = subscription(status="canceled")
    stale_copy = subscription(status="active")
    send(client, event("customer.subscription.created", stale_copy))
    assert fake_store.get_subscription(USER_ID)["plan"] == "free"  # type: ignore[index]


def test_cancelling_at_period_end_keeps_pro_until_then(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription(cancel_at_period_end=True)
    send(client, event("customer.subscription.updated", {"id": "sub_1"}))
    row = fake_store.get_subscription(USER_ID)
    assert row is not None
    assert row["plan"] == "pro"
    assert row["cancel_at_period_end"] is True


def test_a_cancelled_subscription_downgrades_the_account(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription()
    send(client, event("customer.subscription.created", {"id": "sub_1"}, "evt_1"))
    gateway.subscriptions["sub_1"] = subscription(status="canceled")
    send(client, event("customer.subscription.deleted", {"id": "sub_1"}, "evt_2"))
    row = fake_store.get_subscription(USER_ID)
    assert row is not None
    assert row["plan"] == "free"
    assert row["status"] == "canceled"
    assert plans.entitlements(row).analyses_limit == 1


def test_an_old_subscription_ending_doesnt_undo_a_newer_one(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_new"] = subscription("sub_new")
    send(client, event("customer.subscription.created", {"id": "sub_new"}, "evt_1"))
    gateway.subscriptions["sub_old"] = subscription("sub_old", status="canceled")
    send(client, event("customer.subscription.deleted", {"id": "sub_old"}, "evt_2"))
    row = fake_store.get_subscription(USER_ID)
    assert row is not None
    assert row["plan"] == "pro"
    assert row["stripe_subscription_id"] == "sub_new"


def test_a_failed_payment_keeps_pro_while_stripe_retries_and_then_ends_it(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription()
    send(client, event("customer.subscription.created", {"id": "sub_1"}, "evt_1"))
    gateway.subscriptions["sub_1"] = subscription(status="past_due")
    invoice = {"id": "in_1", "parent": {"subscription_details": {"subscription": "sub_1"}}}
    send(client, event("invoice.payment_failed", invoice, "evt_2"))
    row = fake_store.get_subscription(USER_ID)
    assert row is not None
    assert (row["plan"], row["status"]) == ("pro", "past_due")
    gateway.subscriptions["sub_1"] = subscription(status="unpaid")
    send(client, event("customer.subscription.updated", {"id": "sub_1"}, "evt_3"))
    assert fake_store.get_subscription(USER_ID)["plan"] == "free"  # type: ignore[index]


def test_a_finished_pro_checkout_upgrades_without_waiting_for_other_events(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.subscriptions["sub_1"] = subscription()
    session = {"id": "cs_1", "mode": "subscription", "subscription": "sub_1", "payment_status": "paid"}
    send(client, event("checkout.session.completed", session))
    assert fake_store.get_subscription(USER_ID)["plan"] == "pro"  # type: ignore[index]


def test_a_subscription_is_found_by_customer_when_metadata_is_missing(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    fake_store.update_subscription(USER_ID, {"stripe_customer_id": "cus_7"})
    sub = subscription(customer="cus_7")
    sub["metadata"] = {}
    gateway.subscriptions["sub_1"] = sub
    send(client, event("customer.subscription.created", {"id": "sub_1"}))
    assert fake_store.get_subscription(USER_ID)["plan"] == "pro"  # type: ignore[index]


def test_a_paid_report_checkout_records_the_purchase(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    session = {
        "id": "cs_9",
        "mode": "payment",
        "payment_status": "paid",
        "metadata": {"kind": "report", "user_id": USER_ID, "analysis_id": "a1"},
    }
    send(client, event("checkout.session.completed", session))
    assert fake_store.purchased_report_ids(USER_ID) == {"a1"}
    assert fake_store.report_purchases["a1"]["reference"] == "cs_9"


def test_an_unpaid_report_checkout_records_nothing(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    session = {
        "id": "cs_9",
        "mode": "payment",
        "payment_status": "unpaid",
        "metadata": {"kind": "report", "user_id": USER_ID, "analysis_id": "a1"},
    }
    send(client, event("checkout.session.completed", session))
    assert fake_store.purchased_report_ids(USER_ID) == set()


def test_other_events_are_accepted_and_ignored(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway
) -> None:
    response = send(client, event("customer.created", {"id": "cus_1"}))
    assert response.status_code == 200
    assert fake_store.stripe_events == {}


def test_a_failure_while_handling_lets_stripe_send_the_event_again(
    fake_store: FakeStore, gateway: FakeGateway
) -> None:
    gateway.read_error = stripe.APIConnectionError("Stripe unreachable")
    payload = event("customer.subscription.updated", {"id": "sub_1"})
    client = TestClient(app, raise_server_exceptions=False)
    response = send(client, payload)
    assert response.status_code == 500
    # Not marked as handled, so the retry is processed.
    assert fake_store.stripe_events == {}
    gateway.read_error = None
    gateway.subscriptions["sub_1"] = subscription()
    assert send(client, payload).status_code == 200
    assert fake_store.get_subscription(USER_ID)["plan"] == "pro"  # type: ignore[index]


# --- Deleting an account ---


def test_deleting_an_account_ends_its_stripe_billing_first(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(account, "delete_auth_user", deleted.append)
    fake_store.update_subscription(USER_ID, {"stripe_customer_id": "cus_5"})
    assert client.delete("/account", headers=auth_headers()).status_code == 204
    assert gateway.deleted_customers == ["cus_5"]
    assert deleted == [USER_ID]


def test_if_billing_cant_be_stopped_the_account_is_kept(
    client: TestClient, fake_store: FakeStore, gateway: FakeGateway, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(account, "delete_auth_user", deleted.append)
    fake_store.update_subscription(USER_ID, {"stripe_customer_id": "cus_5"})
    gateway.delete_error = stripe.APIConnectionError("Stripe unreachable")
    response = client.delete("/account", headers=auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "billing_unavailable"
    assert deleted == []
    assert fake_store.calls == []  # files untouched


def test_an_account_that_never_paid_is_deleted_without_stripe(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(account, "delete_auth_user", deleted.append)

    def no_stripe() -> billing.Gateway:
        raise billing.BillingUnavailable

    monkeypatch.setattr(account, "gateway_factory", no_stripe)
    assert client.delete("/account", headers=auth_headers()).status_code == 204
    assert deleted == [USER_ID]
