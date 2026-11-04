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


@router.get("/me", response_model=MeResponse)
def me(user: User) -> MeResponse:
    return MeResponse(id=user.id, email=user.email)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: User) -> None:
    # Files go first: if this fails the account still exists, so the user can retry.
    store.delete_all_user_files(user.id)
    delete_auth_user(user.id)
