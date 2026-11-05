import logging
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from kombu.exceptions import OperationalError
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app import market_lookup, store
from app.auth import CurrentUser, get_current_user
from app.scoring import ScoreResult
from app.tasks import run_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analyses")

User = Annotated[CurrentUser, Depends(get_current_user)]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StartAnalysisRequest(CamelModel):
    document_id: UUID
    role: str = Field(min_length=2, max_length=200)
    region: str | None = Field(default=None, max_length=60)


class AnalysisStarted(CamelModel):
    analysis_id: str


class AnalysisResponse(CamelModel):
    id: str
    status: Literal["pending", "processing", "completed", "failed"]
    document_id: str | None
    role: str | None
    region: str | None
    score: int | None
    result: ScoreResult | None
    error_code: str | None
    created_at: str
    completed_at: str | None


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})


def _to_response(row: dict[str, Any]) -> AnalysisResponse:
    target = row.get("target_roles") or {}
    return AnalysisResponse(
        id=row["id"],
        status=row["status"],
        document_id=row["document_id"],
        role=target.get("title"),
        region=target.get("region"),
        score=None if row["score"] is None else round(row["score"]),
        result=row["result"],
        error_code=row["error_code"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=AnalysisStarted)
def start_analysis(user: User, body: StartAnalysisRequest) -> AnalysisStarted:
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

    role = body.role.strip()
    try:
        province = market_lookup.resolve_region(body.region)
        match = market_lookup.resolve_occupation(role, store)
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
    row = store.insert_analysis(
        {"user_id": user.id, "target_role_id": target_role_id, "document_id": document_id}
    )
    try:
        run_analysis.apply_async(
            args=[row["id"], match["occupation_code"], match["occupation_name"], province],
            retry=False,
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


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: UUID, user: User) -> AnalysisResponse:
    row = store.get_analysis(str(analysis_id), user.id)
    if row is None:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Analysis not found.")
    return _to_response(row)
