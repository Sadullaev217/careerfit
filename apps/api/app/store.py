"""Server-side Supabase access. The secret key bypasses RLS, so callers must scope by user id."""

from datetime import date
from functools import lru_cache
from typing import Any

import httpx

from app.config import settings

DOCUMENT_COLUMNS = (
    "id,user_id,type,file_name,file_path,url,status,error_code,"
    "extraction_status,extraction_error,created_at"
)
ANALYSIS_COLUMNS = (
    "id,user_id,document_id,status,score,result,error_code,created_at,completed_at,"
    "target_roles(title,region)"
)
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


def get_parsed_text(document_id: str) -> str | None:
    rows = _rows(
        _client().get(
            "/rest/v1/documents", params={"id": f"eq.{document_id}", "select": "parsed_text"}
        )
    )
    return rows[0]["parsed_text"] if rows else None


def match_skill(embedding: list[float]) -> dict[str, Any] | None:
    rows = _rows(
        _client().post("/rest/v1/rpc/match_skill", json={"query_embedding": embedding})
    )
    return rows[0] if rows else None


def upsert_skills(rows: list[dict[str, Any]]) -> None:
    _client().post(
        "/rest/v1/skills",
        params={"on_conflict": "esco_id"},
        headers={"Prefer": "resolution=merge-duplicates"},
        json=rows,
    ).raise_for_status()


def save_extraction(
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
    _client().post(
        "/rest/v1/extracted_profiles",
        params={"on_conflict": "document_id"},
        headers={"Prefer": "resolution=merge-duplicates"},
        json={
            "document_id": document_id,
            "user_id": user_id,
            "data": profile,
            "prompt_version": prompt_version,
            "model": model,
            "truncated": truncated,
            "suspicious_content": suspicious_content,
            "matched_skills": matched_skills,
        },
    ).raise_for_status()
    # The newest resume replaces the skill list, so old resumes can't keep inflating it.
    _client().delete(
        "/rest/v1/profile_skills", params={"user_id": f"eq.{user_id}"}
    ).raise_for_status()
    if skills:
        _client().post("/rest/v1/profile_skills", json=skills).raise_for_status()


def get_extracted_profile(document_id: str, user_id: str) -> dict[str, Any] | None:
    rows = _rows(
        _client().get(
            "/rest/v1/extracted_profiles",
            params={
                "document_id": f"eq.{document_id}",
                "user_id": f"eq.{user_id}",
                "select": (
                    "data,matched_skills,prompt_version,model,truncated,suspicious_content,created_at"
                ),
            },
        )
    )
    return rows[0] if rows else None


def _upsert(table: str, conflict_columns: str, rows: list[dict[str, Any]]) -> None:
    _client().post(
        f"/rest/v1/{table}",
        params={"on_conflict": conflict_columns},
        headers={"Prefer": "resolution=merge-duplicates"},
        json=rows,
    ).raise_for_status()


def upsert_postings(rows: list[dict[str, Any]]) -> None:
    _upsert("job_postings", "source,source_id", rows)


def delete_postings_before(cutoff: date) -> None:
    _client().delete(
        "/rest/v1/job_postings", params={"posted_at": f"lt.{cutoff.isoformat()}"}
    ).raise_for_status()


def upsert_occupations(rows: list[dict[str, Any]]) -> None:
    _upsert("occupations", "code", rows)


def upsert_occupation_titles(rows: list[dict[str, Any]]) -> None:
    _upsert("occupation_titles", "title,occupation_code", rows)


def replace_occupation_skills(rows: list[dict[str, Any]]) -> None:
    _upsert("occupation_skills", "occupation_code,skill_id", rows)


def _all_skills() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_size = 1000
    while True:
        page = _rows(
            _client().get(
                "/rest/v1/skills",
                params={"select": "id,name,esco_id", "esco_id": "not.is.null", "order": "id"},
                headers={"Range": f"{len(rows)}-{len(rows) + page_size - 1}"},
            )
        )
        rows += page
        if len(page) < page_size:
            return rows


def skill_ids_by_esco_uri() -> dict[str, str]:
    return {row["esco_id"]: row["id"] for row in _all_skills()}


def skill_names_by_esco_uri() -> dict[str, str]:
    return {row["esco_id"]: row["name"] for row in _all_skills()}


def match_occupation(embedding: list[float]) -> dict[str, Any] | None:
    rows = _rows(
        _client().post("/rest/v1/rpc/match_occupation", json={"query_embedding": embedding})
    )
    return rows[0] if rows else None


def market_stats(occupation_code: str, region: str | None) -> dict[str, Any]:
    response = _client().post(
        "/rest/v1/rpc/market_stats", json={"p_code": occupation_code, "p_region": region}
    )
    response.raise_for_status()
    stats: dict[str, Any] = response.json()
    return stats


def occupation_skills(occupation_code: str) -> list[dict[str, Any]]:
    return _rows(
        _client().get(
            "/rest/v1/occupation_skills",
            params={
                "occupation_code": f"eq.{occupation_code}",
                "select": "required,rank,skills(name,esco_id)",
                # Ties need a fixed order: a reshuffled list would be a different question for the AI.
                "order": "rank,skill_id",
            },
        )
    )


def get_or_create_target_role(user_id: str, title: str, region: str) -> str:
    rows = _rows(
        _client().get(
            "/rest/v1/target_roles",
            params={
                "user_id": f"eq.{user_id}",
                "title": f"eq.{title}",
                "region": f"eq.{region}",
                "select": "id",
                "limit": "1",
            },
        )
    )
    if rows:
        return str(rows[0]["id"])
    response = _client().post(
        "/rest/v1/target_roles",
        params={"select": "id"},
        headers={"Prefer": "return=representation"},
        json={"user_id": user_id, "title": title, "region": region},
    )
    return str(_rows(response)[0]["id"])


def insert_analysis(row: dict[str, Any]) -> dict[str, Any]:
    response = _client().post(
        "/rest/v1/analyses",
        params={"select": ANALYSIS_COLUMNS},
        headers={"Prefer": "return=representation"},
        json=row,
    )
    return _rows(response)[0]


def get_analysis(analysis_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    params = {"id": f"eq.{analysis_id}", "select": ANALYSIS_COLUMNS}
    if user_id is not None:
        params["user_id"] = f"eq.{user_id}"
    rows = _rows(_client().get("/rest/v1/analyses", params=params))
    return rows[0] if rows else None


def list_analyses(user_id: str) -> list[dict[str, Any]]:
    return _rows(
        _client().get(
            "/rest/v1/analyses",
            params={
                "user_id": f"eq.{user_id}",
                "select": ANALYSIS_COLUMNS,
                "order": "created_at.desc",
            },
        )
    )


def update_analysis(analysis_id: str, fields: dict[str, Any]) -> None:
    _client().patch(
        "/rest/v1/analyses", params={"id": f"eq.{analysis_id}"}, json=fields
    ).raise_for_status()


def get_skill_judgement(document_id: str, key: str) -> dict[str, Any] | None:
    rows = _rows(
        _client().get(
            "/rest/v1/skill_judgements",
            params={
                "document_id": f"eq.{document_id}",
                "input_key": f"eq.{key}",
                "select": "result",
            },
        )
    )
    if not rows:
        return None
    result: dict[str, Any] = rows[0]["result"]
    return result


def save_skill_judgement(document_id: str, key: str, result: dict[str, Any]) -> None:
    _upsert(
        "skill_judgements",
        "document_id,input_key",
        [{"document_id": document_id, "input_key": key, "result": result}],
    )


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
