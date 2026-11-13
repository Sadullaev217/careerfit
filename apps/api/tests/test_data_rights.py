"""Retention, export and account deletion: the person's rights over their data."""

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app import retention
from app.revenuecat import RevenueCatUnavailable
from app.routers import account
from tests.helpers import OTHER_USER_ID, USER_ID, FakeStore, auth_headers

NOW = datetime(2026, 11, 13, tzinfo=UTC)


def add_document(store: FakeStore, days_old: int, user_id: str = USER_ID, **changes: Any) -> str:
    row = store.insert_document(
        {
            "user_id": user_id,
            "type": "resume",
            "file_name": "cv.pdf",
            "file_path": f"{user_id}/{days_old}.pdf",
            "parsed_text": "Senior nurse, Mercy Hospital",
            "created_at": (NOW - timedelta(days=days_old)).isoformat(),
            **changes,
        }
    )
    if row.get("file_path"):
        store.files[row["file_path"]] = b"%PDF-1.7 file"
    return str(row["id"])


# --- Retention ---


def test_the_deletion_date_is_ninety_days_after_upload() -> None:
    row = {"type": "resume", "created_at": "2026-11-01T10:00:00+00:00"}
    assert retention.delete_after(row) == "2027-01-30T10:00:00+00:00"
    assert retention.delete_after({**row, "keep": True}) is None
    assert retention.delete_after({**row, "file_deleted_at": "2026-12-01T00:00:00+00:00"}) is None
    assert retention.delete_after({**row, "type": "portfolio_link"}) is None


def test_old_files_are_deleted_unless_kept(fake_store: FakeStore) -> None:
    old = add_document(fake_store, 91)
    kept = add_document(fake_store, 200, keep=True)
    recent = add_document(fake_store, 89)
    link = add_document(
        fake_store, 300, type="portfolio_link", file_path=None, url="https://github.com/x"
    )

    assert retention.delete_expired_files(fake_store, NOW) == 1

    gone = fake_store.documents[old]
    assert gone["file_path"] is None
    assert gone["parsed_text"] is None
    assert gone["file_deleted_at"] == NOW.isoformat()
    assert f"{USER_ID}/91.pdf" not in fake_store.files
    for untouched in (kept, recent, link):
        assert not fake_store.documents[untouched].get("file_deleted_at")
    assert f"{USER_ID}/200.pdf" in fake_store.files
    # Running again finds nothing new.
    assert retention.delete_expired_files(fake_store, NOW) == 0


def test_a_store_that_never_records_the_deletion_cant_loop_forever() -> None:
    class Stuck:
        calls = 0

        def documents_to_expire(self, cutoff: datetime, limit: int) -> list[dict[str, Any]]:
            self.calls += 1
            return [{"id": "x", "file_path": "u/x.pdf"}]

        def delete_files(self, paths: list[str]) -> None:
            pass

        def expire_document(self, document_id: str, at: datetime) -> None:
            pass

    stuck = Stuck()
    retention.delete_expired_files(stuck, NOW)
    assert stuck.calls == retention.MAX_BATCHES


def test_people_can_keep_a_file(client: TestClient, fake_store: FakeStore) -> None:
    document_id = add_document(fake_store, 10)
    listed = client.get("/documents", headers=auth_headers()).json()[0]
    assert listed["keep"] is False
    assert listed["deleteAfter"].startswith((NOW + timedelta(days=80)).date().isoformat())

    kept = client.patch(f"/documents/{document_id}", headers=auth_headers(), json={"keep": True})
    assert kept.status_code == 200
    assert kept.json()["keep"] is True
    assert kept.json()["deleteAfter"] is None
    assert fake_store.documents[document_id]["keep"] is True


def test_only_stored_files_of_ones_own_can_be_kept(
    client: TestClient, fake_store: FakeStore
) -> None:
    theirs = add_document(fake_store, 10, user_id=OTHER_USER_ID)
    response = client.patch(f"/documents/{theirs}", headers=auth_headers(), json={"keep": True})
    assert response.status_code == 404
    gone = add_document(fake_store, 100, file_deleted_at=NOW.isoformat(), file_path=None)
    response = client.patch(f"/documents/{gone}", headers=auth_headers(), json={"keep": True})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "nothing_to_keep"


# --- Export ---


def read_zip(content: bytes) -> tuple[dict[str, Any], dict[str, bytes]]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    data: dict[str, Any] = json.loads(files.pop("data.json"))
    return data, files


def test_export_has_every_table_and_the_files(client: TestClient, fake_store: FakeStore) -> None:
    document_id = add_document(fake_store, 5, file_name="../../My CV (final).pdf")
    fake_store.accept_consent(USER_ID, "2026-11-13.self_hosted")
    add_document(fake_store, 5, user_id=OTHER_USER_ID)

    response = client.get("/account/export", headers=auth_headers())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "careerfit-data.zip" in response.headers["content-disposition"]
    data, files = read_zip(response.content)

    assert data["account"]["id"] == USER_ID
    assert [row["id"] for row in data["tables"]["documents"]] == [document_id]
    assert data["tables"]["documents"][0]["parsed_text"] == "Senior nurse, Mercy Hospital"
    assert data["tables"]["consents"][0]["version"] == "2026-11-13.self_hosted"
    stored = [name for name in files if name.startswith("files/")]
    # The name is made safe to unpack: no folders or odd characters from the original name.
    assert stored == [f"files/{document_id}-My CV _final_.pdf"]
    assert files[stored[0]] == b"%PDF-1.7 file"
    assert "README.txt" in files


def test_export_notes_files_it_couldnt_read(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id = add_document(fake_store, 5)

    def missing(path: str) -> bytes:
        raise httpx.HTTPStatusError(
            "gone", request=httpx.Request("GET", "http://x"), response=httpx.Response(404)
        )

    monkeypatch.setattr(fake_store, "download_file", missing)
    data, files = read_zip(client.get("/account/export", headers=auth_headers()).content)
    assert data["documents_whose_file_could_not_be_read"] == [document_id]
    assert not [name for name in files if name.startswith("files/")]


def test_export_needs_sign_in(client: TestClient, fake_store: FakeStore) -> None:
    assert client.get("/account/export").status_code == 401


# --- Deletion ---


class FakeRevenueCat:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.deleted: list[str] = []

    def subscriber(self, app_user_id: str) -> dict[str, Any]:
        return {}

    def delete_subscriber(self, app_user_id: str) -> None:
        if self.fail:
            raise RevenueCatUnavailable
        self.deleted.append(app_user_id)


def test_deletion_removes_revenuecats_record_too(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []
    records = FakeRevenueCat()
    monkeypatch.setattr(account, "delete_auth_user", deleted.append)
    monkeypatch.setattr(account, "store_records_factory", lambda: records)
    monkeypatch.setattr(account.settings, "revenuecat_secret_key", "server-only")
    add_document(fake_store, 5)
    assert client.delete("/account", headers=auth_headers()).status_code == 204
    assert records.deleted == [USER_ID]
    assert deleted == [USER_ID]
    assert not [path for path in fake_store.files if path.startswith(f"{USER_ID}/")]


def test_if_revenuecat_cant_be_reached_nothing_is_deleted(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(account, "delete_auth_user", deleted.append)
    monkeypatch.setattr(account, "store_records_factory", lambda: FakeRevenueCat(fail=True))
    monkeypatch.setattr(account.settings, "revenuecat_secret_key", "server-only")
    add_document(fake_store, 5)
    response = client.delete("/account", headers=auth_headers())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "purchase_records_unavailable"
    assert deleted == []
    assert fake_store.files


def test_without_revenuecat_set_up_it_isnt_called(
    client: TestClient, fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    def never() -> FakeRevenueCat:
        raise AssertionError("RevenueCat isn't set up here")

    monkeypatch.setattr(account, "delete_auth_user", lambda _user_id: None)
    monkeypatch.setattr(account, "store_records_factory", never)
    assert client.delete("/account", headers=auth_headers()).status_code == 204
