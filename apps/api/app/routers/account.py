from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app import billing, consent, plans, store
from app.auth import CurrentUser, delete_auth_user, get_current_user
from app.rate_limit import per_user

router = APIRouter()

# Replaced in tests. Raises BillingUnavailable when Stripe isn't set up on this server.
gateway_factory = billing.default_gateway

User = Annotated[CurrentUser, Depends(get_current_user)]


class MeResponse(BaseModel):
    id: str
    email: str | None


class PlanResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    plan: Literal["free", "pro"]
    status: str
    provider: str | None
    cancel_at_period_end: bool
    current_period_end: str | None
    analyses_used: int
    analyses_limit: int | None
    limit_resets_at: str
    purchased_reports: list[str]


class ConsentResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    version: str
    accepted: bool
    accepted_at: str | None
    # Where resumes are read, so the agreement screen can say so.
    ai_processing: consent.AiProcessing


class AcceptConsentRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    version: str = Field(min_length=1, max_length=40)


@router.get("/me", response_model=MeResponse)
def me(user: User) -> MeResponse:
    return MeResponse(id=user.id, email=user.email)


@router.get("/account/plan", response_model=PlanResponse)
def account_plan(user: User) -> PlanResponse:
    entitlements = plans.entitlements(store.get_subscription(user.id))
    now = datetime.now(UTC)
    return PlanResponse(
        plan=entitlements.plan,
        status=entitlements.status,
        provider=entitlements.provider,
        cancel_at_period_end=entitlements.cancel_at_period_end,
        current_period_end=entitlements.current_period_end,
        analyses_used=store.count_analyses_since(user.id, plans.month_start(now)),
        analyses_limit=entitlements.analyses_limit,
        # A plain date: the limit resets at midnight UTC, and apps show this as that calendar day.
        limit_resets_at=plans.next_month_start(now).date().isoformat(),
        purchased_reports=sorted(store.purchased_report_ids(user.id)),
    )


@router.get("/account/consent", response_model=ConsentResponse)
def get_consent(user: User) -> ConsentResponse:
    row = consent.current(store, user.id)
    return ConsentResponse(
        version=consent.current_version(),
        accepted=row is not None,
        accepted_at=str(row["accepted_at"]) if row else None,
        ai_processing=consent.ai_processing(),
    )


@router.post(
    "/account/consent",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(per_user("consent", "30/hour"))],
)
def accept_consent(user: User, body: AcceptConsentRequest) -> None:
    # The screen sends the version it showed, so nobody accepts a version they didn't see.
    if body.version != consent.current_version():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "consent_outdated",
                "message": "The policy changed while this page was open. Please review it again.",
            },
        )
    store.accept_consent(user.id, body.version)


@router.delete(
    "/account/consent",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(per_user("consent", "30/hour"))],
)
def withdraw_consent(user: User) -> None:
    store.withdraw_consent(user.id, consent.current_version())


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(per_user("account-delete", "5/hour"))])
def delete_account(user: User) -> None:
    # Billing goes first, then files: if either fails the account still exists, so the user can retry.
    if (store.get_subscription(user.id) or {}).get("stripe_customer_id"):
        try:
            billing.forget_customer(user.id, store, gateway_factory())
        except billing.BillingUnavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "billing_unavailable",
                    "message": "We couldn't cancel your subscription, so your account wasn't deleted. "
                    "Please try again.",
                },
            ) from None
    store.delete_all_user_files(user.id)
    delete_auth_user(user.id)
