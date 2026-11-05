import time
from typing import Any
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

SUPABASE_URL = "https://test.supabase.co"
USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())

VALID_PROFILE: dict[str, Any] = {
    "skills": [
        {"name": "Python", "name_en": "Python", "level": "advanced", "years": 5, "confidence": 1},
        {"name": "SQL", "name_en": "SQL", "level": "unknown", "years": None, "confidence": 0.9},
    ],
    "work_history": [
        {
            "title": "Developer",
            "title_en": "Developer",
            "employer": "Acme",
            "start_date": "2020-01",
            "end_date": None,
            "is_current": True,
            "confidence": 1,
        }
    ],
    "education": [
        {
            "degree": "BSc",
            "field_of_study": "Computing",
            "institution": "Riverton University",
            "end_year": 2019,
            "confidence": 1,
        }
    ],
    "certifications": [{"name": "AWS Developer", "issuer": "Amazon", "year": 2021, "confidence": 1}],
    "languages": [{"name_en": "English", "level": "native", "confidence": 1}],
    "projects": [{"name": "Ledger", "demonstrates_en": ["Python"], "confidence": 1}],
    "industry_en": "Software",
    "industry_confidence": 0.9,
    "seniority": "mid",
    "seniority_confidence": 0.8,
    "flags": [],
}


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
        self.saved_extractions: dict[str, dict[str, Any]] = {}
        self.profile_skills: list[dict[str, Any]] = []
        self.skill_matches: dict[str, dict[str, Any] | None] = {}
        # Keyed by token, like the real table.
        self.push_tokens: dict[str, dict[str, Any]] = {}

    def get_parsed_text(self, document_id: str) -> str | None:
        row = self.documents.get(document_id)
        return row.get("parsed_text") if row else None

    def match_skill(self, embedding: list[float]) -> dict[str, Any] | None:
        return self.skill_matches.get(str(embedding[0]))

    def save_extraction(
        self,
        document_id: str,
        user_id: str,
        profile: dict[str, Any],
        prompt_version: str,
        model: str,
        truncated: bool,
        suspicious_content: bool,
        skills: list[dict[str, Any]],
        matched_skills: list[dict[str, Any]],
    ) -> None:
        self.saved_extractions[document_id] = {
            "user_id": user_id,
            "data": profile,
            "prompt_version": prompt_version,
            "model": model,
            "truncated": truncated,
            "suspicious_content": suspicious_content,
            "matched_skills": matched_skills,
            "created_at": "2026-11-04T00:00:00+00:00",
        }
        self.profile_skills = skills

    def get_extracted_profile(self, document_id: str, user_id: str) -> dict[str, Any] | None:
        row = self.saved_extractions.get(document_id)
        return row if row and row["user_id"] == user_id else None

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

    def save_push_token(self, user_id: str, token: str, platform: str, language: str) -> None:
        self.push_tokens[token] = {"user_id": user_id, "platform": platform, "language": language}

    def delete_push_token(self, user_id: str, token: str) -> None:
        row = self.push_tokens.get(token)
        if row and row["user_id"] == user_id:
            del self.push_tokens[token]

    def list_push_tokens(self, user_id: str) -> list[dict[str, Any]]:
        return [
            {"token": token, "platform": row["platform"], "language": row["language"]}
            for token, row in self.push_tokens.items()
            if row["user_id"] == user_id
        ]

    def forget_push_tokens(self, tokens: list[str]) -> None:
        for token in tokens:
            self.push_tokens.pop(token, None)
