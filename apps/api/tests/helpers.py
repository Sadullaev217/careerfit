import time
from typing import Any
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

SUPABASE_URL = "https://test.supabase.co"
USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
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


def auth_headers(user_id: str = USER_ID) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub=user_id)}"}


class FakeStore:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.files: dict[str, bytes] = {}
        self.calls: list[str] = []
        self.download_error: Exception | None = None
        self.download_calls = 0

    def insert_document(self, row: dict[str, Any]) -> dict[str, Any]:
        document_id = row.get("id") or str(uuid4())
        stored = {
            "id": document_id,
            "file_name": None,
            "file_path": None,
            "url": None,
            "status": "pending",
            "error_code": None,
            "created_at": "2026-11-04T00:00:00+00:00",
            **row,
        }
        self.documents[document_id] = stored
        return dict(stored)

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.documents.values() if row["user_id"] == user_id]

    def get_document(self, document_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        row = self.documents.get(document_id)
        if row is None or (user_id is not None and row["user_id"] != user_id):
            return None
        return dict(row)

    def update_document(self, document_id: str, fields: dict[str, Any]) -> None:
        if document_id in self.documents:
            self.documents[document_id].update(fields)

    def delete_document(self, document_id: str) -> None:
        self.documents.pop(document_id, None)

    def upload_file(self, path: str, data: bytes, content_type: str) -> None:
        self.files[path] = data

    def download_file(self, path: str) -> bytes:
        self.download_calls += 1
        if self.download_error:
            raise self.download_error
        return self.files[path]

    def delete_files(self, paths: list[str]) -> None:
        for path in paths:
            self.files.pop(path, None)

    def delete_all_user_files(self, user_id: str) -> None:
        self.calls.append(f"delete_all_user_files:{user_id}")
        self.files = {k: v for k, v in self.files.items() if not k.startswith(f"{user_id}/")}
