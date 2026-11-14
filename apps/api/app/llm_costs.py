"""What AI calls cost, per person, and alerts when a day's spending passes the budget.

A job wraps its AI calls in `metering(user_id, job, store)`. The AI clients report each call's tokens and
cost with `record()`, which adds them to the job's meter, if there is one. When the job ends, one row per
model goes to the llm_usage table and one `llm_usage` event to analytics. Only counts are kept, never
text. A failure to save them is logged and never fails the job.

`check_budgets` runs every hour from Celery beat and alerts, at most once a day for each budget, when the
day's total or one person's total passes LLM_DAILY_BUDGET_USD or LLM_USER_DAILY_BUDGET_USD.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from app import analytics
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelUsage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: Decimal = field(default_factory=Decimal)


@dataclass
class Meter:
    user_id: str
    job: str
    models: dict[str, ModelUsage] = field(default_factory=dict)

    def add(self, model: str, prompt_tokens: int, completion_tokens: int, cost_usd: Decimal) -> None:
        usage = self.models.setdefault(model, ModelUsage())
        usage.calls += 1
        usage.prompt_tokens += prompt_tokens
        usage.completion_tokens += completion_tokens
        usage.cost_usd += cost_usd


_current: ContextVar[Meter | None] = ContextVar("llm_meter", default=None)


class UsageStore(Protocol):
    def record_llm_usage(self, rows: list[dict[str, Any]]) -> None: ...

    def llm_costs_since(self, start: datetime) -> list[dict[str, Any]]: ...


def record(model: str, prompt_tokens: int, completion_tokens: int, cost_usd: float | str = 0) -> None:
    """Called by the AI clients after each answer. Does nothing outside a metered job."""
    meter = _current.get()
    if meter is not None:
        meter.add(model, max(prompt_tokens, 0), max(completion_tokens, 0), Decimal(str(cost_usd)))


@contextmanager
def metering(user_id: str, job: str, store: UsageStore) -> Iterator[Meter]:
    meter = Meter(user_id, job)
    token = _current.set(meter)
    try:
        yield meter
    finally:
        _current.reset(token)
        _save(meter, store)


def _save(meter: Meter, store: UsageStore) -> None:
    if not meter.models:
        return
    rows: list[dict[str, Any]] = [
        {
            "user_id": meter.user_id,
            "job": meter.job,
            "model": model,
            "calls": usage.calls,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_usd": str(usage.cost_usd),
        }
        for model, usage in meter.models.items()
    ]
    try:
        store.record_llm_usage(rows)
    except Exception as exc:  # noqa: BLE001 - the job's result matters more than its bill
        logger.warning("Could not save AI usage for job %s: %s", meter.job, type(exc).__name__)
    for row in rows:
        analytics.capture(
            meter.user_id,
            "llm_usage",
            {key: row[key] for key in ("job", "model", "calls", "prompt_tokens", "completion_tokens")}
            | {"cost_usd": float(row["cost_usd"])},
        )


@dataclass(frozen=True)
class BudgetAlert:
    key: str
    message: str


def over_budget(rows: list[dict[str, Any]], day: str) -> list[BudgetAlert]:
    """The budgets today's rows have passed. Each alert's key is the same all day, to send it once."""
    per_user: dict[str, Decimal] = {}
    for row in rows:
        per_user[row["user_id"]] = per_user.get(row["user_id"], Decimal()) + Decimal(
            str(row["cost_usd"])
        )
    alerts = []
    total = sum(per_user.values(), Decimal())
    budget = Decimal(str(settings.llm_daily_budget_usd))
    if total > budget:
        alerts.append(
            BudgetAlert(
                f"llm-budget:{day}:total",
                f"AI spending today is ${total:.2f}, over the daily budget of ${budget:.2f}",
            )
        )
    user_budget = Decimal(str(settings.llm_user_daily_budget_usd))
    for user_id, spent in sorted(per_user.items()):
        if spent > user_budget:
            # The account id, never an email, so the alert carries nothing personal.
            alerts.append(
                BudgetAlert(
                    f"llm-budget:{day}:user:{user_id}",
                    f"Account {user_id} used ${spent:.2f} of AI today, over the "
                    f"per-person budget of ${user_budget:.2f}",
                )
            )
    return alerts


def check_budgets(
    store: UsageStore,
    first_time: Callable[[str], bool],
    send: Callable[[str], None],
    now: datetime | None = None,
) -> list[BudgetAlert]:
    """Sends each new alert. `first_time(key)` is true only the first time it sees a key."""
    now = now or datetime.now(UTC)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sent = []
    for alert in over_budget(store.llm_costs_since(start), start.date().isoformat()):
        if first_time(alert.key):
            send(alert.message)
            sent.append(alert)
    return sent
