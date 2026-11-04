import time

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from tests.helpers import USER_ID, FakeStore, make_token


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


def test_delete_account_removes_files_then_the_user(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_store.upload_file(f"{USER_ID}/a.pdf", b"x", "application/pdf")
    fake_store.upload_file("someone-else/b.pdf", b"y", "application/pdf")

    def fake_delete(user_id: str) -> None:
        fake_store.calls.append(f"delete_auth_user:{user_id}")

    monkeypatch.setattr("app.routers.account.delete_auth_user", fake_delete)
    response = client.delete("/account", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 204
    assert fake_store.calls == [f"delete_all_user_files:{USER_ID}", f"delete_auth_user:{USER_ID}"]
    assert list(fake_store.files) == ["someone-else/b.pdf"]


def test_delete_account_keeps_user_if_files_cannot_be_removed(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []

    def failing(_user_id: str) -> None:
        raise RuntimeError("storage down")

    monkeypatch.setattr(fake_store, "delete_all_user_files", failing)
    monkeypatch.setattr("app.routers.account.delete_auth_user", deleted.append)
    no_raise = TestClient(client.app, raise_server_exceptions=False)
    response = no_raise.delete("/account", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 500
    assert deleted == []


def test_delete_account_requires_auth(client: TestClient) -> None:
    assert client.delete("/account").status_code == 401
