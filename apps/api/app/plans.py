"""What each plan allows. Payments decide the plan; these rules decide what the plan means.

Free: one analysis a calendar month (UTC), plus the history list, the progress view and the three
general resume rewordings every report already has. Pro: unlimited analyses and rewriting the resume for
a chosen job. A detailed PDF report is a separate one-time purchase for one analysis, on any plan.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

FREE_ANALYSES_PER_MONTH = 1

# Stripe keeps a subscription "past_due" while it retries a failed payment. Access continues during those
# retries; it ends when Stripe gives up and cancels, or marks the subscription unpaid.
PRO_STATUSES = frozenset({"active", "trialing", "past_due"})

Plan = Literal["free", "pro"]


@dataclass(frozen=True)
class Entitlements:
    plan: Plan
    status: str
    provider: str | None
    cancel_at_period_end: bool
    current_period_end: str | None
    analyses_limit: int | None  # None means unlimited

    @property
    def is_pro(self) -> bool:
        return self.plan == "pro"


def _expired(row: dict[str, Any], now: datetime) -> bool:
    # Store plans have no webhook telling us they ended, so their saved end date decides. Stripe sends events.
    end = row.get("current_period_end")
    if row.get("provider") != "revenuecat" or not end:
        return False
    return datetime.fromisoformat(str(end).replace("Z", "+00:00")) <= now


def entitlements(subscription: dict[str, Any] | None, now: datetime | None = None) -> Entitlements:
    """Reads the stored subscription row. A missing row is a free account."""
    row = subscription or {}
    status = str(row.get("status") or "active")
    is_pro = (
        row.get("plan") == "pro"
        and status in PRO_STATUSES
        and not _expired(row, now or datetime.now(UTC))
    )
    return Entitlements(
        plan="pro" if is_pro else "free",
        status=status,
        provider=row.get("provider"),
        cancel_at_period_end=bool(row.get("cancel_at_period_end")),
        current_period_end=row.get("current_period_end"),
        analyses_limit=None if is_pro else FREE_ANALYSES_PER_MONTH,
    )


def month_start(now: datetime) -> datetime:
    return now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def next_month_start(now: datetime) -> datetime:
    start = month_start(now)
    return start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
