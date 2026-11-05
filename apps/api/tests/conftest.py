from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import auth, tasks
from app.celery_app import celery_app
from app.config import settings
from app.main import app
from app.routers import account, documents, notifications
from tests.helpers import PRIVATE_KEY, SUPABASE_URL, FakeStore


class _NoQueue:
    def apply_async(self, args: list[str], retry: bool = True) -> None:
        pass


@pytest.fixture(autouse=True)
def isolated_from_local_settings() -> Iterator[None]:
    # A developer's .env may turn on inline jobs, which would run real AI during tests.
    previous = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = False
    yield
    celery_app.conf.task_always_eager = previous


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "supabase_url", SUPABASE_URL)
    monkeypatch.setattr(settings, "supabase_secret_key", "server-key")
    monkeypatch.setattr(auth, "_signing_key", lambda _token: PRIVATE_KEY.public_key())
    yield TestClient(app)


@pytest.fixture
def fake_store(monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr(documents, "store", fake)
    monkeypatch.setattr(account, "store", fake)
    monkeypatch.setattr(notifications, "store", fake)
    monkeypatch.setattr(tasks, "store", fake)
    monkeypatch.setattr(tasks, "extract_resume", _NoQueue())
    return fake
