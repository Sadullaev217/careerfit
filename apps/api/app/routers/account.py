from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app import store
from app.auth import CurrentUser, delete_auth_user, get_current_user

router = APIRouter()

User = Annotated[CurrentUser, Depends(get_current_user)]


class MeResponse(BaseModel):
    id: str
    email: str | None


class PlanResponse(BaseModel):
    plan: str
    status: str


@router.get("/me", response_model=MeResponse)
def me(user: User) -> MeResponse:
    return MeResponse(id=user.id, email=user.email)


@router.get("/account/plan", response_model=PlanResponse)
def account_plan(user: User) -> PlanResponse:
    row = store.get_subscription(user.id)
    return PlanResponse(plan=row["plan"] if row else "free", status=row["status"] if row else "active")


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: User) -> None:
    # Files go first: if this fails the account still exists, so the user can retry.
    store.delete_all_user_files(user.id)
    delete_auth_user(user.id)
