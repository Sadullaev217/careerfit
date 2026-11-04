from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app import auth, tasks
from app.config import settings
from app.main import app
from app.routers import account, documents
from tests.helpers import PRIVATE_KEY, SUPABASE_URL, FakeStore


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
    monkeypatch.setattr(tasks, "store", fake)
    return fake
