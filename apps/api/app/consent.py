"""The agreement people accept before CareerFit reads a resume: the privacy policy, the terms, and AI
processing by the provider this server uses.

The version names the policy date and the AI provider, so switching to a hosted model asks everyone again.
Uploading, analysing and tailoring need the current version; reading, exporting and deleting never do,
so people can always see, take or remove their data.
"""

from typing import Any, Literal, Protocol

from fastapi import HTTPException, status

from app.config import settings

# Change when the privacy policy or terms change in a way people must agree to again.
POLICY_DATE = "2026-11-24"

AiProcessing = Literal["self_hosted", "openrouter"]


class ConsentStore(Protocol):
    def get_consent(self, user_id: str, version: str) -> dict[str, Any] | None: ...


def ai_processing() -> AiProcessing:
    return "openrouter" if settings.llm_provider == "openrouter" else "self_hosted"


def current_version() -> str:
    return f"{POLICY_DATE}.{ai_processing()}"


def current(store: ConsentStore, user_id: str) -> dict[str, Any] | None:
    """The person's acceptance of the current version, unless they withdrew it."""
    row = store.get_consent(user_id, current_version())
    return row if row and not row.get("withdrawn_at") else None


def require(store: ConsentStore, user_id: str) -> None:
    if current(store, user_id) is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "consent_required",
                "message": "Please review and accept the privacy policy and terms first.",
            },
        )
