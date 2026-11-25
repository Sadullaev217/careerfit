"""Server-side Supabase access. The secret key bypasses RLS, so callers must scope by user id."""

from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any

import httpx

from app.config import settings

DOCUMENT_COLUMNS = (
    "id,user_id,type,file_name,file_path,url,status,error_code,"
    "extraction_status,extraction_error,keep,file_deleted_at,created_at"
)

# Every table holding one person's data, and the column naming them. The export reads all of them, and
# account deletion relies on each cascading from auth.users. A database test checks this list is complete.
USER_TABLES: dict[str, str] = {
    "profiles": "id",
    "documents": "user_id",
    "extracted_profiles": "user_id",
    "profile_skills": "user_id",
    "target_roles": "user_id",
    "analyses": "user_id",
    "recommendations": "user_id",
    "tailored_rewrites": "user_id",
    "report_purchases": "user_id",
    "subscriptions": "user_id",
    "consents": "user_id",
    "push_tokens": "user_id",
    "llm_usage": "user_id",
}
# Tables keyed by one of the person's documents rather than by the person.
DOCUMENT_TABLES: dict[str, str] = {"skill_judgements": "document_id"}
# The export leaves out search embeddings, which are lists of numbers that mean nothing to a person.
EXPORT_COLUMNS = {
    "documents": "id,type,file_name,file_path,url,parsed_text,status,error_code,extraction_status,"
    "extraction_error,keep,file_deleted_at,created_at",
}
ANALYSIS_COLUMNS = (
    "id,user_id,document_id,status,stage,score,result,error_code,created_at,completed_at,"
    "target_roles(title,region)"
)
_LIST_PAGE_SIZE = 1000
_TRANSLATIONS_PER_REQUEST = 50
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
    rows = _rows(_client().post("/rest/v1/rpc/match_skill", json={"query_embedding": embedding}))
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


def get_occupation(code: str) -> dict[str, Any] | None:
    rows = _rows(
        _client().get("/rest/v1/occupations", params={"code": f"eq.{code}", "select": "code,name"})
    )
    if not rows:
        return None
    return {"occupation_code": rows[0]["code"], "occupation_name": rows[0]["name"]}


def search_occupation_titles(query: str, count: int) -> list[dict[str, Any]]:
    """The query must already be limited to plain words, since * is a wildcard here."""
    rows = _rows(
        _client().get(
            "/rest/v1/occupation_titles",
            params={
                "title": f"ilike.*{query}*",
                "select": "title,occupation_code,occupations(name)",
                "order": "posting_count.desc,title",
                "limit": str(count),
            },
        )
    )
    return [
        {
            "title": row["title"],
            "occupation_code": row["occupation_code"],
            "occupation_name": row["occupations"]["name"],
        }
        for row in rows
    ]


def list_occupations() -> list[dict[str, Any]]:
    return _rows(
        _client().get("/rest/v1/occupations", params={"select": "code,name", "order": "code"})
    )


def get_translations(terms: list[str], language: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for start in range(0, len(terms), _TRANSLATIONS_PER_REQUEST):
        batch = terms[start : start + _TRANSLATIONS_PER_REQUEST]
        # Names contain commas and brackets, which would otherwise end the list early.
        quoted = ",".join(
            '"' + term.replace("\\", "\\\\").replace('"', '\\"') + '"' for term in batch
        )
        rows = _rows(
            _client().get(
                "/rest/v1/term_translations",
                params={
                    "language": f"eq.{language}",
                    "term": f"in.({quoted})",
                    "select": "term,translation",
                },
            )
        )
        found.update({row["term"]: row["translation"] for row in rows})
    return found


def save_translations(translations: dict[str, str], language: str) -> None:
    _upsert(
        "term_translations",
        "term,language",
        [
            {"term": term, "language": language, "translation": translation}
            for term, translation in translations.items()
        ],
    )


SUBSCRIPTION_COLUMNS = (
    "user_id,plan,status,provider,stripe_customer_id,stripe_subscription_id,"
    "current_period_end,cancel_at_period_end"
)


CONSENT_COLUMNS = "version,accepted_at,withdrawn_at"


def get_consent(user_id: str, version: str) -> dict[str, Any] | None:
    rows = _rows(
        _client().get(
            "/rest/v1/consents",
            params={
                "user_id": f"eq.{user_id}",
                "version": f"eq.{version}",
                "select": CONSENT_COLUMNS,
            },
        )
    )
    return rows[0] if rows else None


def accept_consent(user_id: str, version: str) -> None:
    """Records acceptance now, clearing an earlier withdrawal of the same version."""
    _client().post(
        "/rest/v1/consents",
        params={"on_conflict": "user_id,version"},
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        json={
            "user_id": user_id,
            "version": version,
            "accepted_at": datetime.now(UTC).isoformat(),
            "withdrawn_at": None,
        },
    ).raise_for_status()


def withdraw_consent(user_id: str, version: str) -> None:
    _client().patch(
        "/rest/v1/consents",
        params={"user_id": f"eq.{user_id}", "version": f"eq.{version}", "withdrawn_at": "is.null"},
        json={"withdrawn_at": datetime.now(UTC).isoformat()},
    ).raise_for_status()


def get_subscription(user_id: str) -> dict[str, Any] | None:
    rows = _rows(
        _client().get(
            "/rest/v1/subscriptions",
            params={"user_id": f"eq.{user_id}", "select": SUBSCRIPTION_COLUMNS},
        )
    )
    return rows[0] if rows else None


def find_subscription_by_customer(customer_id: str) -> dict[str, Any] | None:
    rows = _rows(
        _client().get(
            "/rest/v1/subscriptions",
            params={"stripe_customer_id": f"eq.{customer_id}", "select": SUBSCRIPTION_COLUMNS},
        )
    )
    return rows[0] if rows else None


def update_subscription(user_id: str, fields: dict[str, Any]) -> None:
    _client().patch(
        "/rest/v1/subscriptions",
        params={"user_id": f"eq.{user_id}"},
        json={**fields, "updated_at": datetime.now(UTC).isoformat()},
    ).raise_for_status()


def stripe_event_seen(event_id: str) -> bool:
    rows = _rows(
        _client().get("/rest/v1/stripe_events", params={"id": f"eq.{event_id}", "select": "id"})
    )
    return bool(rows)


def record_stripe_event(event_id: str, event_type: str) -> None:
    _client().post(
        "/rest/v1/stripe_events",
        params={"on_conflict": "id"},
        headers={"Prefer": "resolution=ignore-duplicates,return=minimal"},
        json={"id": event_id, "type": event_type},
    ).raise_for_status()


def record_report_purchase(user_id: str, analysis_id: str, provider: str, reference: str) -> None:
    # A second payment for the same analysis is ignored here; it shows up in Stripe for a refund.
    _client().post(
        "/rest/v1/report_purchases",
        params={"on_conflict": "analysis_id"},
        headers={"Prefer": "resolution=ignore-duplicates,return=minimal"},
        json={
            "user_id": user_id,
            "analysis_id": analysis_id,
            "provider": provider,
            "provider_reference": reference,
        },
    ).raise_for_status()


def report_reference_used(reference: str) -> bool:
    rows = _rows(
        _client().get(
            "/rest/v1/report_purchases",
            params={"provider_reference": f"eq.{reference}", "select": "id"},
        )
    )
    return bool(rows)


def purchased_report_ids(user_id: str) -> set[str]:
    rows = _rows(
        _client().get(
            "/rest/v1/report_purchases",
            params={"user_id": f"eq.{user_id}", "select": "analysis_id"},
        )
    )
    return {str(row["analysis_id"]) for row in rows}


def get_tailored_rewrites(analysis_id: str, user_id: str) -> list[dict[str, Any]] | None:
    rows = _rows(
        _client().get(
            "/rest/v1/tailored_rewrites",
            params={
                "analysis_id": f"eq.{analysis_id}",
                "user_id": f"eq.{user_id}",
                "select": "rewrites",
            },
        )
    )
    return list(rows[0]["rewrites"]) if rows else None


def save_tailored_rewrites(
    analysis_id: str, user_id: str, rewrites: list[dict[str, Any]], model: str, prompt_version: str
) -> None:
    _client().post(
        "/rest/v1/tailored_rewrites",
        params={"on_conflict": "analysis_id"},
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        json={
            "analysis_id": analysis_id,
            "user_id": user_id,
            "rewrites": rewrites,
            "model": model,
            "prompt_version": prompt_version,
        },
    ).raise_for_status()


def count_analyses_since(user_id: str, start: datetime) -> int:
    rows = _rows(
        _client().get(
            "/rest/v1/analyses",
            params={
                "user_id": f"eq.{user_id}",
                "created_at": f"gte.{start.isoformat()}",
                "status": "neq.failed",
                "select": "id",
            },
        )
    )
    return len(rows)


def start_analysis_within_limit(
    user_id: str, target_role_id: str, document_id: str, limit: int | None, period_start: datetime
) -> dict[str, Any] | None:
    """Creates the analysis, or returns None when the monthly limit is already used."""
    response = _client().post(
        "/rest/v1/rpc/start_analysis_within_limit",
        json={
            "p_user_id": user_id,
            "p_target_role_id": target_role_id,
            "p_document_id": document_id,
            "p_limit": limit,
            "p_period_start": period_start.isoformat(),
        },
    )
    response.raise_for_status()
    new_id = response.json()
    return get_analysis(str(new_id), user_id) if new_id else None


def match_occupations(embedding: list[float], count: int) -> list[dict[str, Any]]:
    return _rows(
        _client().post(
            "/rest/v1/rpc/match_occupations",
            json={"query_embedding": embedding, "match_count": count},
        )
    )


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


def export_rows(user_id: str) -> dict[str, list[dict[str, Any]]]:
    client = _client()
    tables: dict[str, list[dict[str, Any]]] = {}
    for table, column in USER_TABLES.items():
        params = {column: f"eq.{user_id}", "select": EXPORT_COLUMNS.get(table, "*")}
        tables[table] = _rows(client.get(f"/rest/v1/{table}", params=params))
    ids = [str(row["id"]) for row in tables["documents"]]
    for table, column in DOCUMENT_TABLES.items():
        params = {column: f"in.({','.join(ids)})", "select": "*"}
        tables[table] = _rows(client.get(f"/rest/v1/{table}", params=params)) if ids else []
    return tables


def set_document_keep(document_id: str, user_id: str, keep: bool) -> None:
    _client().patch(
        "/rest/v1/documents",
        params={"id": f"eq.{document_id}", "user_id": f"eq.{user_id}"},
        json={"keep": keep},
    ).raise_for_status()


def documents_to_expire(cutoff: datetime, limit: int) -> list[dict[str, Any]]:
    return _rows(
        _client().get(
            "/rest/v1/documents",
            params={
                "created_at": f"lt.{cutoff.isoformat()}",
                "keep": "eq.false",
                "file_deleted_at": "is.null",
                "type": "neq.portfolio_link",
                "select": "id,file_path",
                "order": "created_at",
                "limit": str(limit),
            },
        )
    )


def expire_document(document_id: str, at: datetime) -> None:
    _client().patch(
        "/rest/v1/documents",
        params={"id": f"eq.{document_id}"},
        json={
            "file_path": None,
            "parsed_text": None,
            "embedding": None,
            "file_deleted_at": at.isoformat(),
        },
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


def save_push_token(user_id: str, token: str, platform: str, language: str) -> None:
    # A phone that signs in to another account takes its token with it.
    _client().post(
        "/rest/v1/push_tokens",
        params={"on_conflict": "token"},
        headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        json={
            "token": token,
            "user_id": user_id,
            "platform": platform,
            "language": language,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    ).raise_for_status()


def delete_push_token(user_id: str, token: str) -> None:
    _client().delete(
        "/rest/v1/push_tokens", params={"token": f"eq.{token}", "user_id": f"eq.{user_id}"}
    ).raise_for_status()


def list_push_tokens(user_id: str) -> list[dict[str, Any]]:
    return _rows(
        _client().get(
            "/rest/v1/push_tokens",
            params={"user_id": f"eq.{user_id}", "select": "token,platform,language"},
        )
    )


def forget_push_tokens(tokens: list[str]) -> None:
    """For tokens the push service says no longer reach a phone."""
    quoted = ",".join(f'"{token}"' for token in tokens)
    _client().delete("/rest/v1/push_tokens", params={"token": f"in.({quoted})"}).raise_for_status()


def record_llm_usage(rows: list[dict[str, Any]]) -> None:
    _client().post(
        "/rest/v1/llm_usage", json=rows, headers={"Prefer": "return=minimal"}
    ).raise_for_status()


def llm_costs_since(start: datetime) -> list[dict[str, Any]]:
    """Each AI job's cost since `start`: user_id and cost_usd only."""
    rows: list[dict[str, Any]] = []
    for page in range(_MAX_LIST_PAGES):
        first = page * _LIST_PAGE_SIZE
        batch = _rows(
            _client().get(
                "/rest/v1/llm_usage",
                params={
                    "select": "user_id,cost_usd",
                    "created_at": f"gte.{start.isoformat()}",
                    "order": "id",
                },
                headers={"Range": f"{first}-{first + _LIST_PAGE_SIZE - 1}"},
            )
        )
        rows.extend(batch)
        if len(batch) < _LIST_PAGE_SIZE:
            break
    return rows


def ping() -> None:
    """Raises when the database can't be reached. Reads one row id from a small table."""
    _client().get(
        "/rest/v1/consents", params={"select": "version", "limit": "1"}
    ).raise_for_status()


def _count(table: str, params: dict[str, str]) -> int:
    response = _client().get(
        f"/rest/v1/{table}",
        params={**params, "select": "id", "limit": "1"},
        headers={"Prefer": "count=exact"},
    )
    response.raise_for_status()
    # Content-Range looks like "0-0/42", or "*/0" when nothing matched.
    return int(response.headers.get("content-range", "*/0").rsplit("/", 1)[-1])


def count_ai_jobs_since(start: datetime, user_id: str | None = None) -> int:
    """Resumes and cover letters read, plus analyses run, since start: by one account, or by everyone.

    Counted two ways and the larger wins. The rows count a job the moment it starts, but a document that
    was uploaded and deleted leaves no row; llm_usage keeps a row for every finished AI job even then.
    """
    since = f"gte.{start.isoformat()}"
    owner = {"user_id": f"eq.{user_id}"} if user_id else {}
    documents = _count(
        "documents", {"created_at": since, "type": "in.(resume,cover_letter)", **owner}
    )
    analyses = _count("analyses", {"created_at": since, **owner})
    return max(documents + analyses, _count("llm_usage", {"created_at": since, **owner}))


def accounts_created_before(cutoff: datetime) -> list[dict[str, Any]]:
    """Account ids and sign-up times older than cutoff, from Supabase's admin API."""
    found: list[dict[str, Any]] = []
    for page in range(1, _MAX_LIST_PAGES + 1):
        response = _client().get(
            "/auth/v1/admin/users", params={"page": str(page), "per_page": str(_LIST_PAGE_SIZE)}
        )
        response.raise_for_status()
        users = response.json().get("users", [])
        for user in users:
            created = datetime.fromisoformat(str(user["created_at"]).replace("Z", "+00:00"))
            if created < cutoff:
                found.append({"id": user["id"], "created_at": user["created_at"]})
        if len(users) < _LIST_PAGE_SIZE:
            break
    return found
