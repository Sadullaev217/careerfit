from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

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
async def delete_account(user: User) -> None:
    await delete_auth_user(user.id)
