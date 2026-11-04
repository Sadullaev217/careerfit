"""Server-side Supabase access. The secret key bypasses RLS, so callers must scope by user id."""

from functools import lru_cache
from typing import Any

import httpx

from app.config import settings

DOCUMENT_COLUMNS = "id,user_id,type,file_name,file_path,url,status,error_code,created_at"
_LIST_PAGE_SIZE = 1000
_MAX_LIST_PAGES = 100


@lru_cache(maxsize=1)
def _client() -> httpx.Client:
    key = settings.supabase_secret_key
    return httpx.Client(
        base_url=settings.supabase_url,
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
        timeout=30,
    )


def _rows(response: httpx.Response) -> list[dict[str, Any]]:
    response.raise_for_status()
    rows: list[dict[str, Any]] = response.json()
    return rows


def insert_document(row: dict[str, Any]) -> dict[str, Any]:
    response = _client().post(
        "/rest/v1/documents",
        params={"select": DOCUMENT_COLUMNS},
        headers={"Prefer": "return=representation"},
        json=row,
    )
    return _rows(response)[0]


def list_documents(user_id: str) -> list[dict[str, Any]]:
    return _rows(
        _client().get(
            "/rest/v1/documents",
            params={
                "user_id": f"eq.{user_id}",
                "select": DOCUMENT_COLUMNS,
                "order": "created_at.desc",
            },
        )
    )


def get_document(document_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    params = {"id": f"eq.{document_id}", "select": DOCUMENT_COLUMNS}
    if user_id is not None:
        params["user_id"] = f"eq.{user_id}"
    rows = _rows(_client().get("/rest/v1/documents", params=params))
    return rows[0] if rows else None


def update_document(document_id: str, fields: dict[str, Any]) -> None:
    _client().patch(
        "/rest/v1/documents", params={"id": f"eq.{document_id}"}, json=fields
    ).raise_for_status()


def delete_document(document_id: str) -> None:
    _client().delete("/rest/v1/documents", params={"id": f"eq.{document_id}"}).raise_for_status()


def upload_file(path: str, data: bytes, content_type: str) -> None:
    _client().post(
        f"/storage/v1/object/{settings.storage_bucket}/{path}",
        content=data,
        headers={"Content-Type": content_type},
    ).raise_for_status()


def download_file(path: str) -> bytes:
    response = _client().get(f"/storage/v1/object/{settings.storage_bucket}/{path}")
    response.raise_for_status()
    return response.content


def delete_files(paths: list[str]) -> None:
    _client().request(
        "DELETE",
        f"/storage/v1/object/{settings.storage_bucket}",
        json={"prefixes": paths},
    ).raise_for_status()


def delete_all_user_files(user_id: str) -> None:
    for _ in range(_MAX_LIST_PAGES):
        response = _client().post(
            f"/storage/v1/object/list/{settings.storage_bucket}",
            json={"prefix": user_id, "limit": _LIST_PAGE_SIZE},
        )
        files = _rows(response)
        if not files:
            return
        delete_files([f"{user_id}/{file['name']}" for file in files])
    raise RuntimeError("user files could not be removed")
