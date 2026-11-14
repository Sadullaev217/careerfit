"""Product analytics events from the server, sent to PostHog. Off unless POSTHOG_PROJECT_TOKEN is set.

Only counts, labels and ids go in: never resume text, file names, job titles typed by a person, emails
or anything else they wrote. `capture` drops any property that isn't a number, a boolean or a short
label, so a mistake can't leak text. A failed send is logged and never fails the request or job.
"""

import logging
import re
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Labels the code sets itself, like "extraction" or "qwen3.5:4b". Anything longer or freer is dropped.
_LABEL = re.compile(r"^[A-Za-z0-9_.:/-]{1,80}$")


def _safe(properties: dict[str, Any]) -> dict[str, Any]:
    kept: dict[str, Any] = {}
    for key, value in properties.items():
        if isinstance(value, bool | int | float) or (isinstance(value, str) and _LABEL.match(value)):
            kept[key] = value
    return kept


def capture(distinct_id: str, event: str, properties: dict[str, Any] | None = None) -> None:
    token = settings.posthog_project_token
    if not token:
        return
    body = {
        "api_key": token,
        "event": event,
        "distinct_id": distinct_id,
        "properties": _safe(properties or {}) | {"environment": settings.environment},
    }
    try:
        httpx.post(f"{settings.posthog_host}/i/v0/e/", json=body, timeout=3).raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Analytics event %s not sent: %s", event, type(exc).__name__)
