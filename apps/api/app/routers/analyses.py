import logging
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from kombu.exceptions import OperationalError
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app import consent, market_lookup, plans, report_pdf, store, tailoring
from app.auth import CurrentUser, get_current_user
from app.llm import LLMUnavailable, get_llm
from app.queueing import enqueue
from app.rate_limit import per_user
from app.recommendations import FullResult
from app.tailoring import TailoredRewrite
from app.tasks import run_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses")

User = Annotated[CurrentUser, Depends(get_current_user)]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StartAnalysisRequest(CamelModel):
    document_id: UUID
    role: str = Field(min_length=2, max_length=200)
    # Set when the person picked a suggestion, so a title in any language still finds its occupation.
    occupation_code: str | None = Field(default=None, max_length=10)
    region: str | None = Field(default=None, max_length=60)
    language: Literal["en", "ru"] = "en"


class AnalysisStarted(CamelModel):
    analysis_id: str


class AnalysisResponse(CamelModel):
    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    stage: str | None
    document_id: str | None
    role: str | None
    region: str | None
    score: int | None
    result: FullResult | None
    error_code: str | None
    created_at: str
    completed_at: str | None


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})


def _limit_reached() -> HTTPException:
    return _error(
        status.HTTP_402_PAYMENT_REQUIRED,
        "limit_reached",
        "You've used this month's free analysis. Upgrade to Pro for unlimited analyses, "
        "or try again next month.",
    )


def _to_response(row: dict[str, Any]) -> AnalysisResponse:
    target = row.get("target_roles") or {}
    return AnalysisResponse(
        id=row["id"],
        status=row["status"],
        stage=row.get("stage"),
        document_id=row["document_id"],
        role=target.get("title"),
        region=target.get("region"),
        score=None if row["score"] is None else round(row["score"]),
        result=row["result"],
        error_code=row["error_code"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=AnalysisStarted, dependencies=[Depends(per_user("analyses", "20/hour"))])
def start_analysis(
    user: User, body: StartAnalysisRequest, background: BackgroundTasks
) -> AnalysisStarted:
    consent.require(store, user.id)
    document_id = str(body.document_id)
    document = store.get_document(document_id, user.id)
    if document is None or document["type"] != "resume":
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Resume not found.")
    if document["extraction_status"] != "ready":
        raise _error(
            status.HTTP_409_CONFLICT,
            "resume_not_ready",
            "We haven't finished reading this resume yet. Please try again shortly.",
        )

    # A quick check before any matching work. The database checks again, atomically, when saving.
    limit = plans.entitlements(store.get_subscription(user.id)).analyses_limit
    period_start = plans.month_start(datetime.now(UTC))
    if limit is not None and store.count_analyses_since(user.id, period_start) >= limit:
        raise _limit_reached()

    role = body.role.strip()
    try:
        province = market_lookup.resolve_region(body.region)
        match = (
            store.get_occupation(body.occupation_code)
            if body.occupation_code
            else market_lookup.resolve_occupation(role, store)
        )
        if match is None:
            raise market_lookup.RoleNotFound
    except market_lookup.UnknownRegion:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown_region",
            market_lookup.UNKNOWN_REGION_MESSAGE,
        ) from None
    except market_lookup.RoleNotFound:
        raise _error(
            status.HTTP_404_NOT_FOUND, "role_not_found", market_lookup.ROLE_NOT_FOUND_MESSAGE
        ) from None

    target_role_id = store.get_or_create_target_role(
        user.id, role, province or market_lookup.NATIONAL
    )
    row = store.start_analysis_within_limit(
        user.id, target_role_id, document_id, limit, period_start
    )
    if row is None:
        raise _limit_reached()
    try:
        enqueue(
            run_analysis,
            [row["id"], match["occupation_code"], match["occupation_name"], province, body.language],
            background,
        )
    except OperationalError as exc:
        logger.error("analysis %s could not be queued", row["id"])
        store.update_analysis(row["id"], {"status": "failed", "error_code": "queue_unavailable"})
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "processing_unavailable",
            "We can't score resumes right now. Please try again in a few minutes.",
        ) from exc
    return AnalysisStarted(analysis_id=row["id"])


@router.get("", response_model=list[AnalysisResponse])
def list_analyses(user: User) -> list[AnalysisResponse]:
    return [_to_response(row) for row in store.list_analyses(user.id)]


class ProgressPoint(CamelModel):
    analysis_id: str
    date: str
    score: int


class ProgressTrack(CamelModel):
    role: str
    region: str | None
    points: list[ProgressPoint]
    change: int | None


def _pro_required() -> HTTPException:
    return _error(status.HTTP_402_PAYMENT_REQUIRED, "pro_required", "This is part of CareerFit Pro.")


@router.get("/progress", response_model=list[ProgressTrack])
def progress(user: User) -> list[ProgressTrack]:
    """Each job's score over time, oldest first, most recently checked job first. Free on every plan.

    Runs group by occupation, like the web chart, so the same job checked in English and in Russian is
    one line. The region is shown only when every run used the same one.
    """
    tracks: dict[str, list[tuple[ProgressPoint, str, str | None]]] = {}
    for row in sorted(store.list_analyses(user.id), key=lambda r: str(r["created_at"])):
        result = row.get("result") or {}
        target = row.get("target_roles") or {}
        name = result.get("occupation_name") or target.get("title")
        if row["status"] != "completed" or row["score"] is None or not name:
            continue
        point = ProgressPoint(analysis_id=row["id"], date=row["created_at"], score=round(row["score"]))
        key = str(result.get("occupation_code") or name)
        tracks.setdefault(key, []).append((point, str(name), target.get("region")))
    ordered = sorted(tracks.values(), key=lambda runs: runs[-1][0].date, reverse=True)
    output: list[ProgressTrack] = []
    for runs in ordered:
        points = [point for point, _, _ in runs]
        regions = {region for _, _, region in runs}
        output.append(
            ProgressTrack(
                role=runs[-1][1],
                region=regions.pop() if len(regions) == 1 else None,
                points=points,
                change=points[-1].score - points[0].score if len(points) > 1 else None,
            )
        )
    return output


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: UUID, user: User) -> AnalysisResponse:
    row = store.get_analysis(str(analysis_id), user.id)
    if row is None:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Analysis not found.")
    return _to_response(row)


@router.get("/{analysis_id}/report.pdf", response_class=Response, dependencies=[Depends(per_user("reports", "60/hour"))])
def detailed_report(
    analysis_id: UUID, user: User, language: Literal["en", "ru"] = "en"
) -> Response:
    """The one-time purchase: this result as a PDF. Only for people who bought it for this analysis."""
    row = _finished_analysis(analysis_id, user.id)
    if row["id"] not in store.purchased_report_ids(user.id):
        raise _error(
            status.HTTP_402_PAYMENT_REQUIRED,
            "report_not_purchased",
            "Buy the detailed report for this result to download it.",
        )
    target = row.get("target_roles") or {}
    pdf = report_pdf.build_report_pdf(
        FullResult.model_validate(row["result"]),
        _job_title(row),
        target.get("region"),
        row["created_at"],
        language,
    )
    name = report_pdf.report_file_name(row["created_at"])
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


class TailoredResponse(CamelModel):
    job: str
    # None until the resume has been tailored for this result.
    rewrites: list[TailoredRewrite] | None


def _finished_analysis(analysis_id: UUID, user_id: str) -> dict[str, Any]:
    row = store.get_analysis(str(analysis_id), user_id)
    if row is None:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Analysis not found.")
    if row["status"] != "completed" or not row.get("result"):
        raise _error(
            status.HTTP_409_CONFLICT, "analysis_not_finished", "This result isn't finished yet."
        )
    return row


def _job_title(row: dict[str, Any]) -> str:
    # The job as the person typed it, else the occupation it was matched to. Saved results use snake_case.
    target = row.get("target_roles") or {}
    return str(target.get("title") or row["result"].get("occupation_name") or "")


@router.get("/{analysis_id}/tailored-rewrites", response_model=TailoredResponse)
def get_tailored_rewrites(analysis_id: UUID, user: User) -> TailoredResponse:
    """Rewrites made earlier stay readable, even after Pro ends."""
    row = _finished_analysis(analysis_id, user.id)
    saved = store.get_tailored_rewrites(row["id"], user.id)
    return TailoredResponse(
        job=_job_title(row),
        rewrites=None if saved is None else [TailoredRewrite.model_validate(i) for i in saved],
    )


@router.post("/{analysis_id}/tailored-rewrites", response_model=TailoredResponse, dependencies=[Depends(per_user("tailoring", "20/hour"))])
def tailor_resume(analysis_id: UUID, user: User) -> TailoredResponse:
    """Pro: rewrites resume lines for this result's job. Takes up to a minute on the local AI model."""
    row = _finished_analysis(analysis_id, user.id)
    job = _job_title(row)
    saved = store.get_tailored_rewrites(row["id"], user.id)
    if saved is not None:
        return TailoredResponse(job=job, rewrites=[TailoredRewrite.model_validate(i) for i in saved])
    consent.require(store, user.id)
    if not plans.entitlements(store.get_subscription(user.id)).is_pro:
        raise _pro_required()

    resume_text = store.get_parsed_text(row["document_id"]) if row.get("document_id") else None
    if not resume_text and row.get("document_id"):
        document = store.get_document(row["document_id"], user.id)
        if document and document.get("file_deleted_at"):
            raise _error(
                status.HTTP_409_CONFLICT,
                "resume_file_deleted",
                "This resume's file was deleted 90 days after upload. Upload it again to tailor it.",
            )
    llm = get_llm()
    try:
        rewrites = tailoring.tailor(
            resume_text or "", job, tailoring.shown_skills(row["result"]), llm
        )
    except tailoring.NothingToTailor:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "nothing_to_tailor",
            "We couldn't find lines in this resume that show the job's skills.",
        ) from None
    except LLMUnavailable:
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "ai_unavailable",
            "Our AI is busy right now. Please try again in a few minutes.",
        ) from None
    store.save_tailored_rewrites(
        row["id"],
        user.id,
        [rewrite.model_dump(by_alias=True) for rewrite in rewrites],
        llm.model,
        tailoring.PROMPT_VERSION,
    )
    return TailoredResponse(job=job, rewrites=rewrites)
