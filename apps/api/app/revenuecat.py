"""Phone purchases: Pro and detailed reports bought through the App Store or Google Play, via RevenueCat.

The app buys through the store, and RevenueCat confirms the purchase. The API never takes the app's word for
it: it asks RevenueCat's server about the signed-in account (the app logs in to RevenueCat with the same user
id) before changing a plan or unlocking a report. Without webhooks, which need a public address, Pro from the
stores lasts until the expiry RevenueCat reported, and the app asks for a fresh check when it opens.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API_URL = "https://api.revenuecat.com/v1"
PRO_ENTITLEMENT = "pro"
REPORT_PRODUCT = "careerfit_detailed_report"
TIMEOUT_SECONDS = 15


class RevenueCatUnavailable(Exception):
    """Store purchases aren't set up on this server, or RevenueCat can't be reached."""


class PurchaseNotFound(Exception):
    """RevenueCat has no such purchase for this account, or it was already used."""


class SubscriberSource(Protocol):
    def subscriber(self, app_user_id: str) -> dict[str, Any]: ...

    def delete_subscriber(self, app_user_id: str) -> None: ...


class Store(Protocol):
    def get_subscription(self, user_id: str) -> dict[str, Any] | None: ...

    def update_subscription(self, user_id: str, fields: dict[str, Any]) -> None: ...

    def record_report_purchase(
        self, user_id: str, analysis_id: str, provider: str, reference: str
    ) -> None: ...

    def report_reference_used(self, reference: str) -> bool: ...


class RevenueCatClient:
    def __init__(self, secret_key: str, http: httpx.Client | None = None) -> None:
        if not secret_key:
            raise RevenueCatUnavailable
        self._http = http or httpx.Client(timeout=TIMEOUT_SECONDS, trust_env=False)
        self._headers = {"Authorization": f"Bearer {secret_key}", "Accept": "application/json"}

    def subscriber(self, app_user_id: str) -> dict[str, Any]:
        try:
            response = self._http.get(
                f"{API_URL}/subscribers/{quote(app_user_id, safe='')}", headers=self._headers
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("RevenueCat lookup failed: %s", type(exc).__name__)
            raise RevenueCatUnavailable from exc
        subscriber: dict[str, Any] = response.json().get("subscriber") or {}
        return subscriber


    def delete_subscriber(self, app_user_id: str) -> None:
        """Removes RevenueCat's record of this person and their purchase history. Store subscriptions
        themselves are cancelled in the App Store or Google Play."""
        try:
            response = self._http.delete(
                f"{API_URL}/subscribers/{quote(app_user_id, safe='')}",
                headers={**self._headers, "Content-Type": "application/json"},
            )
            if response.status_code != 404:
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("RevenueCat delete failed: %s", type(exc).__name__)
            raise RevenueCatUnavailable from exc


def default_client() -> SubscriberSource:
    return RevenueCatClient(settings.revenuecat_secret_key)


def _parse(moment: str) -> datetime:
    return datetime.fromisoformat(moment.replace("Z", "+00:00"))


def sync_pro(user_id: str, store: Store, source: SubscriberSource, now: datetime | None = None) -> None:
    """Copies the account's store Pro entitlement onto its plan. A Stripe plan is never touched here."""
    now = now or datetime.now(UTC)
    subscriber = source.subscriber(user_id)
    entitlement = (subscriber.get("entitlements") or {}).get(PRO_ENTITLEMENT)
    expires = entitlement.get("expires_date") if entitlement else None
    active = entitlement is not None and (expires is None or _parse(expires) > now)

    row = store.get_subscription(user_id) or {}
    if row.get("provider") == "stripe" and row.get("plan") == "pro":
        return
    if active and entitlement is not None:
        product = (subscriber.get("subscriptions") or {}).get(entitlement.get("product_identifier"), {})
        store.update_subscription(
            user_id,
            {
                "plan": "pro",
                "status": "active",
                "provider": "revenuecat",
                "current_period_end": expires,
                # The person turned off renewal in the store; Pro lasts until the period ends.
                "cancel_at_period_end": bool(product.get("unsubscribe_detected_at")),
            },
        )
    elif row.get("provider") == "revenuecat":
        store.update_subscription(
            user_id,
            {"plan": "free", "status": "expired", "current_period_end": expires, "cancel_at_period_end": False},
        )


def claim_report(
    user_id: str, analysis_id: str, transaction_id: str, store: Store, source: SubscriberSource
) -> None:
    """Unlocks one result's report with one store purchase. Each purchase unlocks one result only."""
    purchases = (source.subscriber(user_id).get("non_subscriptions") or {}).get(REPORT_PRODUCT) or []
    match = next(
        (
            item
            for item in purchases
            if transaction_id and transaction_id in (item.get("id"), item.get("store_transaction_id"))
        ),
        None,
    )
    if match is None:
        raise PurchaseNotFound
    reference = f"revenuecat:{match.get('id') or transaction_id}"
    if store.report_reference_used(reference):
        raise PurchaseNotFound
    store.record_report_purchase(user_id, analysis_id, "revenuecat", reference)
