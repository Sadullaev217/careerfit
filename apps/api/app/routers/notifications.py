from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, status
from pydantic import BaseModel, Field

from app import store
from app.auth import CurrentUser, get_current_user
from app.messages import Language
from app.rate_limit import per_user

router = APIRouter()

User = Annotated[CurrentUser, Depends(get_current_user)]

# The shape Expo gives every push token. Anything else isn't stored.
TOKEN_PATTERN = r"^Expo(nent)?PushToken\[[^\]\s]{1,200}\]$"
MAX_TOKEN_LENGTH = 220


class PushTokenIn(BaseModel):
    token: str = Field(pattern=TOKEN_PATTERN, max_length=MAX_TOKEN_LENGTH)
    platform: Literal["ios", "android"]
    language: Language = "en"


@router.put("/push-tokens", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(per_user("push", "30/hour"))])
def register_push_token(body: PushTokenIn, user: User) -> None:
    store.save_push_token(user.id, body.token, body.platform, body.language)


@router.delete("/push-tokens/{token}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(per_user("push", "30/hour"))])
def remove_push_token(
    token: Annotated[str, Path(pattern=TOKEN_PATTERN, max_length=MAX_TOKEN_LENGTH)], user: User
) -> None:
    # Only the signed-in person's own token can go, so one account can't silence another's alerts.
    store.delete_push_token(user.id, token)
