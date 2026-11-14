from datetime import UTC, datetime

import redis
from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app import malware_scan, store
from app.config import settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        timestamp=datetime.now(UTC).isoformat(),
    )


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


def _check_database() -> str:
    store.ping()
    return "ok"


def _check_queue() -> str:
    if settings.celery_task_always_eager:
        return "not used"
    redis.Redis.from_url(settings.redis_url, socket_timeout=3).ping()
    return "ok"


def _check_scanner() -> str:
    if not malware_scan.enabled():
        return "off"
    return "ok" if malware_scan.ping() else "unavailable"


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness_check(response: Response) -> ReadinessResponse:
    """For uptime checks and deploys: can this server reach what it needs? Names only, no details."""
    checks: dict[str, str] = {}
    for name, check in (
        ("database", _check_database),
        ("queue", _check_queue),
        ("virus_scanner", _check_scanner),
    ):
        try:
            checks[name] = check()
        except Exception:  # noqa: BLE001 - any failure means not ready
            checks[name] = "unavailable"
    ready = all(value != "unavailable" for value in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ok" if ready else "unavailable", checks=checks)
