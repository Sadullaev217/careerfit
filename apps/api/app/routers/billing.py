import logging
from typing import Annotated, Literal
from uuid import UUID

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from starlette.concurrency import run_in_threadpool

from app import billing, plans, revenuecat, store
from app.auth import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing")

User = Annotated[CurrentUser, Depends(get_current_user)]


def get_gateway() -> billing.Gateway:
    try:
        return billing.default_gateway()
    except billing.BillingUnavailable:
        raise _unavailable() from None


Gateway = Annotated[billing.Gateway, Depends(get_gateway)]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CheckoutRequest(CamelModel):
    kind: Literal["pro", "report"]
    analysis_id: UUID | None = None
    language: Literal["en", "ru"] = "en"


class PortalRequest(CamelModel):
    language: Literal["en", "ru"] = "en"


class LinkResponse(BaseModel):
    url: str


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})


def _unavailable() -> HTTPException:
    return _error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "billing_unavailable",
        "Payments aren't available right now. Please try again later.",
    )


@router.post("/checkout", response_model=LinkResponse)
def checkout(user: User, body: CheckoutRequest, gateway: Gateway) -> LinkResponse:
    try:
        if body.kind == "pro":
            if plans.entitlements(store.get_subscription(user.id)).is_pro:
                raise _error(status.HTTP_409_CONFLICT, "already_pro", "You already have Pro.")
            url = billing.pro_checkout_url(user.id, user.email, body.language, store, gateway)
            return LinkResponse(url=url)

        if body.analysis_id is None:
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "analysis_required", "Choose a result first."
            )
        analysis_id = str(body.analysis_id)
        analysis = store.get_analysis(analysis_id, user.id)
        if analysis is None:
            raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Analysis not found.")
        if analysis["status"] != "completed" or not analysis.get("result"):
            raise _error(
                status.HTTP_409_CONFLICT,
                "analysis_not_finished",
                "This result isn't finished yet, so there's no report to buy.",
            )
        if analysis_id in store.purchased_report_ids(user.id):
            raise _error(
                status.HTTP_409_CONFLICT, "already_purchased", "You already have this report."
            )
        url = billing.report_checkout_url(
            user.id, user.email, analysis_id, body.language, store, gateway
        )
        return LinkResponse(url=url)
    except billing.BillingUnavailable:
        raise _unavailable() from None
    except stripe.StripeError as exc:
        logger.error("Stripe refused a checkout: %s", type(exc).__name__)
        raise _unavailable() from None


@router.post("/portal", response_model=LinkResponse)
def portal(user: User, body: PortalRequest, gateway: Gateway) -> LinkResponse:
    try:
        url = billing.portal_url(user.id, body.language, store, gateway)
    except billing.BillingUnavailable:
        raise _unavailable() from None
    except stripe.StripeError as exc:
        logger.error("Stripe refused a portal session: %s", type(exc).__name__)
        raise _unavailable() from None
    if url is None:
        raise _error(
            status.HTTP_404_NOT_FOUND, "no_billing_account", "There are no payments to manage yet."
        )
    return LinkResponse(url=url)


def get_store_source() -> revenuecat.SubscriberSource:
    try:
        return revenuecat.default_client()
    except revenuecat.RevenueCatUnavailable:
        raise _unavailable() from None


StoreSource = Annotated[revenuecat.SubscriberSource, Depends(get_store_source)]


class AppStoreReportRequest(CamelModel):
    analysis_id: UUID
    transaction_id: str = Field(min_length=1, max_length=200)


@router.post("/app-store/sync", status_code=status.HTTP_204_NO_CONTENT)
def sync_app_store(user: User, source: StoreSource) -> None:
    """After a purchase or restore in the app: checks the account with RevenueCat and updates the plan."""
    try:
        revenuecat.sync_pro(user.id, store, source)
    except revenuecat.RevenueCatUnavailable:
        raise _unavailable() from None


@router.post("/app-store/report", status_code=status.HTTP_204_NO_CONTENT)
def claim_app_store_report(user: User, body: AppStoreReportRequest, source: StoreSource) -> None:
    """After buying a report in the app: unlocks it for one result once RevenueCat confirms the purchase."""
    analysis_id = str(body.analysis_id)
    analysis = store.get_analysis(analysis_id, user.id)
    if analysis is None:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Analysis not found.")
    if analysis_id in store.purchased_report_ids(user.id):
        return
    try:
        revenuecat.claim_report(user.id, analysis_id, body.transaction_id, store, source)
    except revenuecat.RevenueCatUnavailable:
        raise _unavailable() from None
    except revenuecat.PurchaseNotFound:
        raise _error(
            status.HTTP_409_CONFLICT,
            "purchase_not_found",
            "We couldn't confirm this purchase with the store yet. Please try again in a moment.",
        ) from None


@router.post("/stripe-webhook", include_in_schema=False)
async def stripe_webhook(request: Request, gateway: Gateway) -> dict[str, bool]:
    payload = await request.body()
    try:
        event = gateway.construct_event(payload, request.headers.get("stripe-signature"))
    except billing.InvalidEvent:
        raise _error(status.HTTP_400_BAD_REQUEST, "invalid_event", "Not a valid Stripe event.") from None
    # The store and Stripe calls block, so they run off the event loop. An error here returns 500, and
    # Stripe sends the event again later.
    await run_in_threadpool(billing.handle_event, event, store, gateway)
    return {"received": True}
