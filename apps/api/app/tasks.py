import logging
from typing import Any

import httpx
from celery.exceptions import SoftTimeLimitExceeded
from kombu.exceptions import OperationalError

from app import portfolio, store
from app.celery_app import celery_app
from app.extraction import ExtractionFailed, extract_profile
from app.llm import LLMUnavailable, get_llm
from app.parsing import ParseFailure, extract_text
from app.skill_matching import profile_skills

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def _read_text(document: dict[str, Any]) -> str:
    if document["type"] == "portfolio_link":
        text = portfolio.read_link(document["url"])
        if not text:
            raise ParseFailure("no_text")
        return text
    extension = document["file_path"].rsplit(".", 1)[-1]
    return extract_text(store.download_file(document["file_path"]), extension)


def _fail(document_id: str, code: str) -> None:
    store.update_document(document_id, {"status": "failed", "error_code": code})


def _fail_extraction(document_id: str, code: str) -> None:
    store.update_document(document_id, {"extraction_status": "failed", "extraction_error": code})


def _queue_extraction(document_id: str) -> None:
    store.update_document(document_id, {"extraction_status": "pending", "extraction_error": None})
    try:
        extract_resume.apply_async(args=[document_id], retry=False)
    except OperationalError:
        logger.error("document %s could not be queued for extraction", document_id)
        _fail_extraction(document_id, "queue_unavailable")


@celery_app.task(  # type: ignore[untyped-decorator]
    name="parse_document",
    bind=True,
    max_retries=MAX_RETRIES,
    soft_time_limit=300,
    time_limit=330,
)
def parse_document(self: Any, document_id: str) -> None:
    """Logs ids and error types only: exception messages could quote resume text."""
    document = store.get_document(document_id)
    if document is None:
        return
    store.update_document(document_id, {"status": "parsing", "error_code": None})

    try:
        text = _read_text(document)
    except (ParseFailure, portfolio.LinkFetchFailed) as exc:
        _fail(document_id, exc.code)
        return
    except SoftTimeLimitExceeded:
        _fail(document_id, "timeout")
        return
    except httpx.HTTPError as exc:
        if self.request.retries < MAX_RETRIES:
            raise self.retry(exc=exc, countdown=2**self.request.retries * 5) from None
        _fail(document_id, "network_error")
        return
    except Exception as exc:
        logger.error("document %s parse failed: %s", document_id, type(exc).__name__)
        _fail(document_id, "parse_error")
        return

    store.update_document(document_id, {"status": "ready", "parsed_text": text})
    if document["type"] == "resume":
        _queue_extraction(document_id)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="extract_resume",
    bind=True,
    max_retries=MAX_RETRIES,
    soft_time_limit=600,
    time_limit=630,
)
def extract_resume(self: Any, document_id: str) -> None:
    document = store.get_document(document_id)
    text = store.get_parsed_text(document_id) if document else None
    if document is None or not text:
        return
    store.update_document(document_id, {"extraction_status": "running", "extraction_error": None})

    try:
        result = extract_profile(text, get_llm())
        skills = profile_skills(result.profile, document["user_id"], document_id, store)
        store.save_extraction(
            document_id,
            document["user_id"],
            result.profile.model_dump(),
            result.prompt_version,
            result.model,
            result.truncated,
            result.suspicious_content,
            skills.rows,
            skills.matches,
        )
    except ExtractionFailed as exc:
        _fail_extraction(document_id, exc.code)
        return
    except SoftTimeLimitExceeded:
        _fail_extraction(document_id, "timeout")
        return
    except (LLMUnavailable, httpx.HTTPError) as exc:
        if self.request.retries < MAX_RETRIES:
            raise self.retry(exc=exc, countdown=2**self.request.retries * 15) from None
        _fail_extraction(document_id, "ai_unavailable")
        return
    except Exception as exc:
        logger.error("document %s extraction failed: %s", document_id, type(exc).__name__)
        _fail_extraction(document_id, "extraction_error")
        return

    store.update_document(document_id, {"extraction_status": "ready", "extraction_error": None})
