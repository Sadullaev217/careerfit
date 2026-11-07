"""Stripe payments: checkout links, the billing portal, and keeping plans in step with Stripe's events.

Stripe is the source of truth. Its events can arrive twice or out of order, so each event is handled once,
and subscription events re-read the subscription from Stripe instead of trusting the copy in the event.
Card details never reach CareerFit: people pay on Stripe's own checkout page.
"""

import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any, Literal, Protocol

import stripe

from app.config import settings
from app.plans import PRO_STATUSES

logger = logging.getLogger(__name__)

PRO_PRICE_KEY = "careerfit_pro_monthly"
REPORT_PRICE_KEY = "careerfit_detailed_report"
# Marks the customer-portal settings that scripts/stripe_setup.py creates.
PORTAL_METADATA = {"app": "careerfit"}

SUBSCRIPTION_EVENTS = frozenset(
    {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}
)
INVOICE_EVENTS = frozenset({"invoice.paid", "invoice.payment_failed"})
CHECKOUT_EVENTS = frozenset({"checkout.session.completed", "checkout.session.async_payment_succeeded"})
HANDLED_EVENTS = SUBSCRIPTION_EVENTS | INVOICE_EVENTS | CHECKOUT_EVENTS

Language = Literal["en", "ru"]


class BillingUnavailable(Exception):
    """Payments aren't set up on this server, or Stripe can't be reached."""


class InvalidEvent(Exception):
    """A webhook call that isn't a genuine, untampered Stripe event."""


class BillingStore(Protocol):
    def get_subscription(self, user_id: str) -> dict[str, Any] | None: ...

    def find_subscription_by_customer(self, customer_id: str) -> dict[str, Any] | None: ...

    def update_subscription(self, user_id: str, fields: dict[str, Any]) -> None: ...

    def stripe_event_seen(self, event_id: str) -> bool: ...

    def record_stripe_event(self, event_id: str, event_type: str) -> None: ...

    def record_report_purchase(
        self, user_id: str, analysis_id: str, provider: str, reference: str
    ) -> None: ...


class Gateway(Protocol):
    """The parts of Stripe CareerFit uses. Tests swap in a fake."""

    def create_customer(self, user_id: str, email: str | None) -> str: ...

    def price_id(self, lookup_key: str) -> str: ...

    def create_checkout(self, params: dict[str, Any]) -> str: ...

    def create_portal(self, customer_id: str, return_url: str) -> str: ...

    def get_subscription(self, subscription_id: str) -> dict[str, Any]: ...

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, Any]: ...

    def delete_customer(self, customer_id: str) -> None: ...


class StripeGateway:
    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        if not secret_key:
            raise BillingUnavailable
        self._client = stripe.StripeClient(secret_key)
        self._webhook_secret = webhook_secret
        self._prices: dict[str, str] = {}
        self._portal: str | None = None

    def create_customer(self, user_id: str, email: str | None) -> str:
        params: dict[str, Any] = {"metadata": {"user_id": user_id}}
        if email:
            params["email"] = email
        # The same key for the same person means a retried request can't create a second customer.
        customer = self._client.v1.customers.create(
            params,  # type: ignore[arg-type]
            {"idempotency_key": f"careerfit-customer-{user_id}"},
        )
        return str(customer.id)

    def price_id(self, lookup_key: str) -> str:
        if lookup_key not in self._prices:
            prices = self._client.v1.prices.list({"lookup_keys": [lookup_key], "active": True, "limit": 1})
            if not prices.data:
                logger.error("Stripe price %s is missing; run scripts/stripe_setup.py", lookup_key)
                raise BillingUnavailable
            self._prices[lookup_key] = str(prices.data[0].id)
        return self._prices[lookup_key]

    def create_checkout(self, params: dict[str, Any]) -> str:
        session = self._client.v1.checkout.sessions.create(params)  # type: ignore[arg-type]
        return str(session.url)

    def create_portal(self, customer_id: str, return_url: str) -> str:
        params: dict[str, Any] = {"customer": customer_id, "return_url": return_url}
        configuration = self._portal_configuration()
        if configuration:
            params["configuration"] = configuration
        session = self._client.v1.billing_portal.sessions.create(params)  # type: ignore[arg-type]
        return str(session.url)

    def _portal_configuration(self) -> str | None:
        if self._portal is None:
            found = self._client.v1.billing_portal.configurations.list({"active": True, "limit": 100})
            self._portal = next(
                (
                    str(item.id)
                    for item in found.data
                    if (item.to_dict().get("metadata") or {}).get("app") == PORTAL_METADATA["app"]
                ),
                "",
            )
        return self._portal or None

    def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        subscription: dict[str, Any] = self._client.v1.subscriptions.retrieve(subscription_id).to_dict()
        return subscription

    def construct_event(self, payload: bytes, signature: str | None) -> dict[str, Any]:
        if not self._webhook_secret or not signature:
            raise InvalidEvent
        try:
            event: dict[str, Any] = self._client.construct_event(
                payload, signature, self._webhook_secret
            ).to_dict()
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise InvalidEvent from exc
        return event

    def delete_customer(self, customer_id: str) -> None:
        try:
            self._client.v1.customers.delete(customer_id)
        except stripe.InvalidRequestError as exc:
            if exc.code != "resource_missing":  # already gone is fine
                raise


@lru_cache(maxsize=2)
def _gateway_for(secret_key: str, webhook_secret: str) -> StripeGateway:
    return StripeGateway(secret_key, webhook_secret)


def default_gateway() -> Gateway:
    # One gateway per key, so its price and portal lookups are cached across requests.
    return _gateway_for(settings.stripe_secret_key, settings.stripe_webhook_secret)


# --- Starting payments ---


def _ensure_customer(
    user_id: str, email: str | None, store: BillingStore, gateway: Gateway
) -> str:
    row = store.get_subscription(user_id) or {}
    if row.get("stripe_customer_id"):
        return str(row["stripe_customer_id"])
    customer_id = gateway.create_customer(user_id, email)
    store.update_subscription(user_id, {"stripe_customer_id": customer_id})
    return customer_id


def _web(language: Language, path: str) -> str:
    return f"{settings.web_url.rstrip('/')}/{language}{path}"


def pro_checkout_url(
    user_id: str, email: str | None, language: Language, store: BillingStore, gateway: Gateway
) -> str:
    customer_id = _ensure_customer(user_id, email, store, gateway)
    return gateway.create_checkout(
        {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": user_id,
            "line_items": [{"price": gateway.price_id(PRO_PRICE_KEY), "quantity": 1}],
            "metadata": {"user_id": user_id, "kind": "pro"},
            "subscription_data": {"metadata": {"user_id": user_id}},
            "locale": language,
            "success_url": _web(language, "/settings?checkout=pro"),
            "cancel_url": _web(language, "/pricing"),
        }
    )


def report_checkout_url(
    user_id: str,
    email: str | None,
    analysis_id: str,
    language: Language,
    store: BillingStore,
    gateway: Gateway,
) -> str:
    customer_id = _ensure_customer(user_id, email, store, gateway)
    metadata = {"user_id": user_id, "kind": "report", "analysis_id": analysis_id}
    return gateway.create_checkout(
        {
            "mode": "payment",
            "customer": customer_id,
            "client_reference_id": user_id,
            "line_items": [{"price": gateway.price_id(REPORT_PRICE_KEY), "quantity": 1}],
            "metadata": metadata,
            "payment_intent_data": {"metadata": metadata},
            "locale": language,
            "success_url": _web(language, f"/analyses/{analysis_id}?checkout=report"),
            "cancel_url": _web(language, f"/analyses/{analysis_id}"),
        }
    )


def forget_customer(user_id: str, store: BillingStore, gateway: Gateway) -> None:
    """Before an account is deleted: deleting the Stripe customer cancels any subscription at once, so
    nobody is charged for an account that no longer exists, and removes their email from Stripe."""
    row = store.get_subscription(user_id) or {}
    if row.get("stripe_customer_id"):
        try:
            gateway.delete_customer(str(row["stripe_customer_id"]))
        except stripe.StripeError as exc:
            raise BillingUnavailable from exc


def portal_url(user_id: str, language: Language, store: BillingStore, gateway: Gateway) -> str | None:
    row = store.get_subscription(user_id) or {}
    customer_id = row.get("stripe_customer_id")
    if not customer_id:
        return None
    return gateway.create_portal(str(customer_id), _web(language, "/settings"))


# --- Keeping plans in step with Stripe ---


def _period_end(subscription: dict[str, Any]) -> str | None:
    # Since Stripe's 2025 API versions, billing periods belong to the subscription's items.
    items = (subscription.get("items") or {}).get("data") or []
    ends = [item["current_period_end"] for item in items if item.get("current_period_end")]
    if not ends:
        return None
    return datetime.fromtimestamp(max(ends), UTC).isoformat()


def sync_subscription(subscription: dict[str, Any], store: BillingStore) -> None:
    """Copies one Stripe subscription onto the account it belongs to."""
    customer_id = str(subscription.get("customer") or "")
    user_id = (subscription.get("metadata") or {}).get("user_id")
    row = store.get_subscription(user_id) if user_id else None
    if row is None and customer_id:
        row = store.find_subscription_by_customer(customer_id)
    if row is None:
        logger.warning("Stripe subscription %s has no CareerFit account", subscription.get("id"))
        return

    status = str(subscription.get("status"))
    active = status in PRO_STATUSES
    if not active:
        # An old subscription ending must not undo a newer one, or a plan bought in the app stores.
        newer = row.get("stripe_subscription_id") not in (None, subscription.get("id"))
        other_provider = row.get("provider") not in (None, "stripe") and row.get("plan") == "pro"
        if newer or other_provider:
            return

    store.update_subscription(
        str(row["user_id"]),
        {
            "plan": "pro" if active else "free",
            "status": status,
            "provider": "stripe",
            "stripe_customer_id": customer_id or row.get("stripe_customer_id"),
            "stripe_subscription_id": subscription.get("id"),
            "current_period_end": _period_end(subscription),
            "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
        },
    )


def _invoice_subscription_id(invoice: dict[str, Any]) -> str | None:
    parent = invoice.get("parent") or {}
    details = parent.get("subscription_details") or {}
    found = details.get("subscription") or invoice.get("subscription")
    return str(found) if found else None


def handle_event(event: dict[str, Any], store: BillingStore, gateway: Gateway) -> None:
    """Applies one verified Stripe event. Raises if it can't, so Stripe sends it again later."""
    event_id, event_type = str(event["id"]), str(event["type"])
    if event_type not in HANDLED_EVENTS or store.stripe_event_seen(event_id):
        return
    obj: dict[str, Any] = event["data"]["object"]

    if event_type in SUBSCRIPTION_EVENTS:
        sync_subscription(gateway.get_subscription(str(obj["id"])), store)
    elif event_type in INVOICE_EVENTS:
        subscription_id = _invoice_subscription_id(obj)
        if subscription_id:
            sync_subscription(gateway.get_subscription(subscription_id), store)
        if event_type == "invoice.payment_failed":
            # Stripe emails the customer and retries; the plan shows "payment failed" until then.
            logger.info("a subscription payment failed (invoice %s)", obj.get("id"))
    elif obj.get("mode") == "subscription" and obj.get("subscription"):
        sync_subscription(gateway.get_subscription(str(obj["subscription"])), store)
    elif obj.get("mode") == "payment" and obj.get("payment_status") == "paid":
        metadata = obj.get("metadata") or {}
        if metadata.get("kind") == "report" and metadata.get("user_id") and metadata.get("analysis_id"):
            store.record_report_purchase(
                str(metadata["user_id"]), str(metadata["analysis_id"]), "stripe", str(obj["id"])
            )

    store.record_stripe_event(event_id, event_type)
