import time
from collections.abc import Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app import auth
from app.config import settings
from app.main import app

SUPABASE_URL = "https://test.supabase.co"
USER_ID = "11111111-1111-1111-1111-111111111111"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())


def make_token(key: Any = PRIVATE_KEY, algorithm: str = "ES256", **overrides: Any) -> str:
    claims = {
        "sub": USER_ID,
        "email": "a@example.com",
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "exp": int(time.time()) + 60,
        **overrides,
    }
    return jwt.encode(claims, key, algorithm=algorithm)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(settings, "supabase_url", SUPABASE_URL)
    monkeypatch.setattr(settings, "supabase_secret_key", "server-key")
    monkeypatch.setattr(auth, "_signing_key", lambda _token: PRIVATE_KEY.public_key())
    yield TestClient(app)


def get_me(client: TestClient, token: str) -> int:
    return client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code


def test_valid_token(client: TestClient) -> None:
    response = client.get("/me", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 200
    assert response.json() == {"id": USER_ID, "email": "a@example.com"}


def test_missing_token(client: TestClient) -> None:
    assert client.get("/me").status_code == 401


def test_expired_token(client: TestClient) -> None:
    assert get_me(client, make_token(exp=int(time.time()) - 60)) == 401


def test_wrong_audience(client: TestClient) -> None:
    assert get_me(client, make_token(aud="anon")) == 401


def test_wrong_issuer(client: TestClient) -> None:
    assert get_me(client, make_token(iss="https://evil.example/auth/v1")) == 401


def test_wrong_signing_key(client: TestClient) -> None:
    assert get_me(client, make_token(key=ec.generate_private_key(ec.SECP256R1()))) == 401


def test_rejects_hs256(client: TestClient) -> None:
    assert get_me(client, make_token(key="x" * 32, algorithm="HS256")) == 401


def test_delete_account_targets_token_user(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []

    async def fake_delete(user_id: str) -> None:
        deleted.append(user_id)

    monkeypatch.setattr("app.routers.account.delete_auth_user", fake_delete)
    response = client.delete("/account", headers={"Authorization": f"Bearer {make_token()}"})
    assert response.status_code == 204
    assert deleted == [USER_ID]


def test_delete_account_requires_auth(client: TestClient) -> None:
    assert client.delete("/account").status_code == 401
