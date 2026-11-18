import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import redis
import sentry_sdk
from celery.exceptions import SoftTimeLimitExceeded
from kombu.exceptions import OperationalError

from app import analytics, llm_costs, portfolio, push, retention, store
from app.analysis import prepare_score_input
from app.celery_app import celery_app
from app.config import settings
from app.embeddings import embed_texts
from app.extraction import ExtractionFailed, extract_profile
from app.job_sources import JobBankProvider
from app.llm import LLMUnavailable, get_llm
from app.localization import localized_score
from app.market_data import refresh_market_data
from app.messages import Language
from app.parsing import ParseFailure, extract_text
from app.recommendations import FullResult, Report, build_report
from app.scoring import NothingToScore, ScoreResult, score_profile
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


@celery_app.task(name="check_llm_budgets")  # type: ignore[untyped-decorator]
def check_llm_budgets_task() -> None:
    def first_time(key: str) -> bool:
        # Kept two days, so each budget alerts at most once a day.
        return bool(redis.Redis.from_url(settings.redis_url).set(key, 1, nx=True, ex=172_800))

    def send(message: str) -> None:
        logger.warning("Budget alert: %s", message)
        sentry_sdk.capture_message(message, level="warning")

    llm_costs.check_budgets(store, first_time, send)


@celery_app.task(name="delete_expired_files")  # type: ignore[untyped-decorator]
def delete_expired_files_task() -> None:
    logger.info("file retention: %d files deleted", retention.delete_expired_files(store))


@celery_app.task(  # type: ignore[untyped-decorator]
    name="extract_resume",
    bind=True,
    max_retries=MAX_RETRIES,
    soft_time_limit=settings.ai_task_time_limit_seconds,
    time_limit=settings.ai_task_time_limit_seconds + 30,
)
def extract_resume(self: Any, document_id: str) -> None:
    document = store.get_document(document_id)
    text = store.get_parsed_text(document_id) if document else None
    if document is None or not text:
        return
    store.update_document(document_id, {"extraction_status": "running", "extraction_error": None})

    try:
        with llm_costs.metering(document["user_id"], "extraction", store):
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
    store.update_analysis(analysis_id, {"status": "failed", "stage": None, "error_code": code})


def _finish_analysis(
    analysis_id: str,
    user_id: str,
    scored: ScoreResult,
    finished_at: datetime,
    report: Report | None = None,
    report_error: str | None = None,
) -> None:
    result = FullResult(**scored.model_dump(), report=report, report_error=report_error)
    store.update_analysis(
        analysis_id,
        {
            "status": "completed",
            "stage": None,
            "score": scored.score,
            "result": result.model_dump(),
            "error_code": None,
            "completed_at": finished_at.isoformat(),
        },
    )
    analytics.capture(
        user_id,
        "analysis_completed",
        {"with_report": report is not None, "report_error": report_error or "none"},
    )
    # A report takes a couple of minutes, so people put the phone down and need telling.
    push.send_report_ready(user_id, analysis_id, push_store=store)


def _end_analysis_early(
    analysis_id: str, user_id: str, scored: ScoreResult | None, finished_at: datetime, code: str
) -> None:
    """A good score is still worth showing when only the recommendations couldn't be made."""
    if scored is None:
        _fail_analysis(analysis_id, code)
    else:
        _finish_analysis(analysis_id, user_id, scored, finished_at, report_error=code)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="run_analysis",
    bind=True,
    max_retries=MAX_RETRIES,
    soft_time_limit=settings.ai_task_time_limit_seconds,
    time_limit=settings.ai_task_time_limit_seconds + 30,
)
def run_analysis(
    self: Any,
    analysis_id: str,
    occupation_code: str,
    occupation_name: str,
    region: str | None,
    language: Language = "en",
) -> None:
    row = store.get_analysis(analysis_id)
    if row is None:
        return
    user_id = row["user_id"]
    extraction = (
        store.get_extracted_profile(row["document_id"], row["user_id"])
        if row["document_id"]
        else None
    )
    if extraction is None:
        _fail_analysis(analysis_id, "resume_not_found")
        return
    store.update_analysis(
        analysis_id, {"status": "processing", "stage": "matching", "error_code": None}
    )

    now = datetime.now(UTC)
    scored: ScoreResult | None = None
    context: dict[str, Any] = {
        "extraction": extraction,
        "document_id": row["document_id"],
        "user_id": row["user_id"],
        "region": region,
        "as_of": now.date(),
        "store": store,
        "llm": get_llm(),
        "embed": embed_texts,
    }
    with llm_costs.metering(user_id, "analysis", store):
        try:
            data = prepare_score_input(
                occupation_code=occupation_code,
                occupation_name=occupation_name,
                language=language,
                **context,
            )
            original = score_profile(data)
            scored = localized_score(original, language, context["llm"], store)
            # Recommendations take another minute or so, and the score shouldn't have to wait for them.
            store.update_analysis(
                analysis_id,
                {"stage": "planning", "score": scored.score, "result": scored.model_dump()},
            )
            report = build_report(
                data=data,
                result=original,
                resume_text=store.get_parsed_text(row["document_id"]),
                on_stage=lambda stage: store.update_analysis(analysis_id, {"stage": stage}),
                **context,
            )
        except SkillJudgementFailed:
            _end_analysis_early(analysis_id, user_id, scored, now,"invalid_model_output")
            return
        except NothingToScore:
            _end_analysis_early(analysis_id, user_id, scored, now,"not_enough_market_data")
            return
        except SoftTimeLimitExceeded:
            _end_analysis_early(analysis_id, user_id, scored, now,"timeout")
            return
        except (LLMUnavailable, httpx.HTTPError) as exc:
            if self.request.retries < MAX_RETRIES:
                raise self.retry(exc=exc, countdown=2**self.request.retries * 15) from None
            _end_analysis_early(analysis_id, user_id, scored, now,"ai_unavailable")
            return
        except Exception as exc:
            logger.error("analysis %s failed: %s", analysis_id, type(exc).__name__)
            _end_analysis_early(analysis_id, user_id, scored, now,"analysis_error")
            return

    _finish_analysis(analysis_id, user_id, scored, now, report=report)
