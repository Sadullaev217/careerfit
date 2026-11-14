import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_check() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data


@pytest.fixture
def ready_parts(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    from app import malware_scan, store
    from app.config import settings
    from app.routers import health

    parts = {"database": True, "queue": True, "scanner": True}

    def database() -> None:
        if not parts["database"]:
            raise ConnectionError("down")

    class Redis:
        @staticmethod
        def from_url(url: str, socket_timeout: float) -> "Redis":
            return Redis()

        def ping(self) -> bool:
            if not parts["queue"]:
                raise ConnectionError("down")
            return True

    monkeypatch.setattr(store, "ping", database)
    monkeypatch.setattr(health.redis, "Redis", Redis)
    monkeypatch.setattr(malware_scan, "ping", lambda: parts["scanner"])
    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    monkeypatch.setattr(settings, "malware_scanner", "clamav")
    return parts


async def ready() -> tuple[int, dict[str, object]]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health/ready")
    return response.status_code, response.json()


@pytest.mark.asyncio
async def test_ready_when_everything_answers(ready_parts: dict[str, bool]) -> None:
    assert await ready() == (
        200,
        {"status": "ok", "checks": {"database": "ok", "queue": "ok", "virus_scanner": "ok"}},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("part", "check"), [("database", "database"), ("queue", "queue"), ("scanner", "virus_scanner")]
)
async def test_not_ready_when_a_part_is_down(
    ready_parts: dict[str, bool], part: str, check: str
) -> None:
    ready_parts[part] = False
    code, body = await ready()
    assert code == 503
    assert body["checks"][check] == "unavailable"  # type: ignore[index]


@pytest.mark.asyncio
async def test_parts_that_are_off_do_not_count(
    ready_parts: dict[str, bool], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "celery_task_always_eager", True)
    monkeypatch.setattr(settings, "malware_scanner", "off")
    code, body = await ready()
    assert code == 200
    assert body["checks"] == {"database": "ok", "queue": "not used", "virus_scanner": "off"}
