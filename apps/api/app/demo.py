"""Settings for running CareerFit as a free public demo. All are off unless set (docs/deployment.md).

- DEMO_MODE: every account gets Pro and every detailed report, and payments are switched off, so
  visitors can try everything without paying.
- DEMO_DAILY_AI_JOBS: how many resumes read plus analyses run, all accounts together, per UTC day. The
  demo's one server and its free AI model can't run more.
- DEMO_USER_DAILY_AI_JOBS: the same for one account, so one visitor can't use up everyone's day.
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
    def count_ai_jobs_since(self, start: datetime, user_id: str | None = None) -> int: ...


def day_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def check_daily_limit(store: JobCounter, user_id: str, now: datetime | None = None) -> None:
    """Raises 429 when today's AI jobs reached DEMO_DAILY_AI_JOBS for everyone together, or
    DEMO_USER_DAILY_AI_JOBS for this account. A limit of 0 means none."""
    now = now or datetime.now(UTC)
    start = day_start(now)
    retry_after = {"Retry-After": str(int((start + timedelta(days=1) - now).total_seconds()))}
    limit = settings.demo_daily_ai_jobs
    if limit > 0 and store.count_ai_jobs_since(start) >= limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "demo_daily_limit",
                "message": "The demo has reached today's limit. Please come back tomorrow.",
            },
            headers=retry_after,
        )
    user_limit = settings.demo_user_daily_ai_jobs
    if user_limit > 0 and store.count_ai_jobs_since(start, user_id) >= user_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "demo_user_daily_limit",
                "message": "You've used today's demo allowance. Please come back tomorrow.",
            },
            headers=retry_after,
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
