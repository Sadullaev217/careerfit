"""Tells a person's phones that a report is ready, through Expo's push service.

The message is fixed text and the analysis id. It never carries a score, a job title or anything from
a resume, because notifications show on lock screens and pass through Apple's and Google's servers.
"""

import logging
from typing import Any, Protocol

import httpx

from app import store
from app.config import settings
from app.messages import say

logger = logging.getLogger(__name__)

SEND_TIMEOUT_SECONDS = 10
# Expo accepts up to 100 messages a request, far more than one person's phones.
MAX_MESSAGES_PER_REQUEST = 100
ANDROID_CHANNEL = "reports"


class PushStore(Protocol):
    def list_push_tokens(self, user_id: str) -> list[dict[str, Any]]: ...

    def forget_push_tokens(self, tokens: list[str]) -> None: ...


def report_ready_messages(tokens: list[dict[str, Any]], analysis_id: str) -> list[dict[str, Any]]:
    return [
        {
            "to": row["token"],
            "title": say(row["language"], "push.report_ready_title"),
            "body": say(row["language"], "push.report_ready_body"),
            "data": {"analysisId": analysis_id},
            "sound": "default",
            "channelId": ANDROID_CHANNEL,
        }
        for row in tokens[:MAX_MESSAGES_PER_REQUEST]
    ]


def send_report_ready(
    user_id: str,
    analysis_id: str,
    push_store: PushStore | None = None,
    http: httpx.Client | None = None,
) -> None:
    """Never raises: a missed alert must not turn a finished analysis into a failed one."""
    source = push_store or store
    try:
        tokens = source.list_push_tokens(user_id)
        if not tokens:
            return
        messages = report_ready_messages(tokens, analysis_id)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if settings.expo_access_token:
            headers["Authorization"] = f"Bearer {settings.expo_access_token}"
        client = http or httpx.Client(timeout=SEND_TIMEOUT_SECONDS, trust_env=False)
        response = client.post(settings.expo_push_url, json=messages, headers=headers)
        response.raise_for_status()
        # Tickets come back in the order the messages were sent.
        tickets = response.json().get("data") or []
        gone = [
            message["to"]
            for message, ticket in zip(messages, tickets, strict=False)
            if ticket.get("status") == "error"
            and (ticket.get("details") or {}).get("error") == "DeviceNotRegistered"
        ]
        if gone:
            source.forget_push_tokens(gone)
    except Exception as exc:
        logger.warning("report-ready alert for analysis %s not sent: %s", analysis_id, type(exc).__name__)
