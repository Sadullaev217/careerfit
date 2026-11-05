import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from celery.exceptions import SoftTimeLimitExceeded
from kombu.exceptions import OperationalError

from app import portfolio, store
from app.analysis import analyze
from app.celery_app import celery_app
from app.embeddings import embed_texts
from app.extraction import ExtractionFailed, extract_profile
from app.job_sources import JobBankProvider
from app.llm import LLMUnavailable, get_llm
from app.market_data import refresh_market_data
from app.parsing import ParseFailure, extract_text
from app.scoring import NothingToScore
from app.skill_judgement import SkillJudgementFailed
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
    name="refresh_market_data",
    bind=True,
    max_retries=2,
    soft_time_limit=1800,
    time_limit=1860,
)
def refresh_market_data_task(self: Any) -> None:
    try:
        summary = refresh_market_data(JobBankProvider(), store, embed_texts)
    except httpx.HTTPError as exc:
        logger.error("market refresh failed: %s", type(exc).__name__)
        raise self.retry(exc=exc, countdown=1800) from None
    logger.info("market refresh: %s", summary)


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


def _fail_analysis(analysis_id: str, code: str) -> None:
    store.update_analysis(analysis_id, {"status": "failed", "error_code": code})


@celery_app.task(  # type: ignore[untyped-decorator]
    name="run_analysis",
    bind=True,
    max_retries=MAX_RETRIES,
    soft_time_limit=600,
    time_limit=630,
)
def run_analysis(
    self: Any, analysis_id: str, occupation_code: str, occupation_name: str, region: str | None
) -> None:
    row = store.get_analysis(analysis_id)
    if row is None:
        return
    extraction = (
        store.get_extracted_profile(row["document_id"], row["user_id"])
        if row["document_id"]
        else None
    )
    if extraction is None:
        _fail_analysis(analysis_id, "resume_not_found")
        return
    store.update_analysis(analysis_id, {"status": "processing", "error_code": None})

    now = datetime.now(UTC)
    try:
        result = analyze(
            extraction=extraction,
            document_id=row["document_id"],
            user_id=row["user_id"],
            occupation_code=occupation_code,
            occupation_name=occupation_name,
            region=region,
            as_of=now.date(),
            store=store,
            llm=get_llm(),
            embed=embed_texts,
        )
    except SkillJudgementFailed:
        _fail_analysis(analysis_id, "invalid_model_output")
        return
    except NothingToScore:
        _fail_analysis(analysis_id, "not_enough_market_data")
        return
    except SoftTimeLimitExceeded:
        _fail_analysis(analysis_id, "timeout")
        return
    except (LLMUnavailable, httpx.HTTPError) as exc:
        if self.request.retries < MAX_RETRIES:
            raise self.retry(exc=exc, countdown=2**self.request.retries * 15) from None
        _fail_analysis(analysis_id, "ai_unavailable")
        return
    except Exception as exc:
        logger.error("analysis %s failed: %s", analysis_id, type(exc).__name__)
        _fail_analysis(analysis_id, "analysis_error")
        return

    store.update_analysis(
        analysis_id,
        {
            "status": "completed",
            "score": result.score,
            "result": result.model_dump(),
            "error_code": None,
            "completed_at": now.isoformat(),
        },
    )
