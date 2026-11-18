"""Settings for running CareerFit as a free public demo. All are off unless set (docs/deployment.md).

- DEMO_MODE: every account gets Pro and every detailed report, and payments are switched off, so
  visitors can try everything without paying.
- DEMO_DAILY_AI_JOBS: how many resumes read plus analyses run, all accounts together, per UTC day. The
  demo's one server can't run more, and the cap stops one visitor from using it all.
- DEMO_ACCOUNT_DAYS: accounts and everything in them are deleted this many days after sign-up.

The sample resume (data/sample-resume.pdf) is a made-up person, so visitors can see a result without
uploading their own.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

SAMPLE_RESUME_PATH = Path(__file__).resolve().parents[1] / "data" / "sample-resume.pdf"
SAMPLE_RESUME_NAME = "Sample resume (Alex Example).pdf"


class JobCounter(Protocol):
    def count_ai_jobs_since(self, start: datetime) -> int: ...


def day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def check_daily_limit(store: JobCounter, now: datetime | None = None) -> None:
    """Raises 429 when today's AI jobs reached DEMO_DAILY_AI_JOBS. No limit when it's 0."""
    limit = settings.demo_daily_ai_jobs
    if limit <= 0:
        return
    now = now or datetime.now(UTC)
    if store.count_ai_jobs_since(day_start(now)) >= limit:
        tomorrow = day_start(now) + timedelta(days=1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "demo_daily_limit",
                "message": "The demo has reached today's limit. Please come back tomorrow.",
            },
            headers={"Retry-After": str(int((tomorrow - now).total_seconds()))},
        )


def payments_off() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND,
        detail={"code": "payments_off", "message": "Payments are off in this demo."},
    )


class AccountLister(Protocol):
    def accounts_created_before(self, cutoff: datetime) -> list[dict[str, Any]]: ...


def delete_expired_accounts(
    store: AccountLister, erase: Callable[[str], None], now: datetime | None = None
) -> int:
    """Erases accounts older than DEMO_ACCOUNT_DAYS. One failure doesn't stop the rest."""
    days = settings.demo_account_days
    if days <= 0:
        return 0
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    erased = 0
    for account in store.accounts_created_before(cutoff):
        try:
            erase(account["id"])
            erased += 1
        except Exception as exc:  # noqa: BLE001 - try again tomorrow
            logger.warning("Could not delete an expired demo account: %s", type(exc).__name__)
    return erased
