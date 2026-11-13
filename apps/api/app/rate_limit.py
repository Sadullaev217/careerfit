"""Request limits, so one account or one address can't use up the AI, storage, Stripe or everyone's share.

Two layers: every address gets a general allowance per minute (the middleware in main.py), and the costly
routes also count per account (`per_user`). Counts live wherever RATE_LIMIT_STORAGE points: Redis in
production, so every API process shares them, and memory for local development and tests.

If the counter store is down, requests go through and the error is logged: a Redis outage shouldn't take
the whole API down with it.
"""

import logging
import time
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from limits import RateLimitItem, parse
from limits.storage import storage_from_string
from limits.strategies import FixedWindowRateLimiter

from app.auth import CurrentUser, get_current_user
from app.config import settings

logger = logging.getLogger(__name__)

MESSAGE = "Too many requests. Please wait a little and try again."

# Per address, across every route except the health check and Stripe's webhook.
PER_ADDRESS = parse("300/minute")

_storage = storage_from_string(settings.rate_limit_storage)
_limiter = FixedWindowRateLimiter(_storage)


class Limited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after


def reset() -> None:
    """Clears every count. For tests."""
    _storage.reset()


def check(item: RateLimitItem, scope: str, key: str) -> None:
    """Counts one request for `key`, raising Limited when it is over the limit."""
    if not settings.rate_limits_enabled:
        return
    try:
        if _limiter.hit(item, scope, key):
            return
        reset_at = _limiter.get_window_stats(item, scope, key).reset_time
    except Exception as exc:  # noqa: BLE001 - any storage failure means "can't count", never "refuse"
        logger.error("rate limit storage unavailable: %s", type(exc).__name__)
        return
    raise Limited(max(1, int(reset_at - time.time()) + 1))


def too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        detail={"code": "rate_limited", "message": MESSAGE},
        headers={"Retry-After": str(retry_after)},
    )


def per_user(scope: str, rate: str) -> Callable[..., None]:
    """A route dependency that allows each account `rate` requests, for example "20/hour"."""
    item = parse(rate)

    def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> None:
        try:
            check(item, scope, user.id)
        except Limited as exc:
            raise too_many(exc.retry_after) from None

    return dependency
