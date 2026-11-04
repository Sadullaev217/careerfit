import logging
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from kombu.exceptions import OperationalError
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app import portfolio, store
from app.auth import CurrentUser, get_current_user
from app.file_validation import MAX_FILE_BYTES, RejectedFile, validate_file
from app.tasks import parse_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents")

User = Annotated[CurrentUser, Depends(get_current_user)]

MAX_FILE_NAME_LENGTH = 200

ERROR_MESSAGES = {
    "no_text": "We couldn't find any text in this file.",
    "ocr_unavailable": "This looks like a scan, and scanned files can't be read right now.",
    "parse_error": "We couldn't read this file. Try exporting it again.",
    "timeout": "Reading this file took too long. Try a smaller file.",
    "network_error": "Something went wrong on our side. Please try again.",
    "link_blocked": "This address can't be reached from our service.",
    "link_disallowed": "This website doesn't allow automated access to this page.",
    "link_unreachable": "We couldn't reach this page. Check that the address is public.",
    "link_too_large": "This page is too large to read.",
    "link_unsupported": "This address doesn't point to a readable web page.",
    "github_not_found": "We couldn't find this GitHub profile.",
    "github_unavailable": "GitHub isn't available right now. Please try again later.",
}


class DocumentResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    type: str
    file_name: str | None
    url: str | None
    status: str
    error_code: str | None
    error_message: str | None
    created_at: str


class PortfolioLinkRequest(BaseModel):
    url: str


def _to_response(row: dict[str, Any]) -> DocumentResponse:
    code = row.get("error_code")
    return DocumentResponse(
        id=row["id"],
        type=row["type"],
        file_name=row.get("file_name"),
        url=row.get("url"),
        status=row["status"],
        error_code=code,
        error_message=ERROR_MESSAGES.get(code) if code else None,
        created_at=row["created_at"],
    )


def _error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})


def _queue_unavailable() -> HTTPException:
    return _error(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "processing_unavailable",
        "We can't process files right now. Please try again in a few minutes.",
    )


def _display_name(name: str | None) -> str:
    base = (name or "document").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(char for char in base if char.isprintable()).strip()
    return cleaned[:MAX_FILE_NAME_LENGTH] or "document"


def _enqueue(document_id: str) -> None:
    parse_document.apply_async(args=[document_id], retry=False)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
def upload_document(
    user: User,
    type: Annotated[Literal["resume", "cover_letter"], Form()],
    file: UploadFile,
) -> DocumentResponse:
    data = file.file.read(MAX_FILE_BYTES + 1)
    try:
        kind = validate_file(data)
    except RejectedFile as exc:
        raise _error(exc.status_code, exc.code, exc.message) from exc

    # The path uses only ids, so a crafted file name can't choose where the file lands.
    document_id = str(uuid4())
    path = f"{user.id}/{document_id}.{kind.extension}"
    store.upload_file(path, data, kind.content_type)
    try:
        row = store.insert_document(
            {
                "id": document_id,
                "user_id": user.id,
                "type": type,
                "file_name": _display_name(file.filename),
                "file_path": path,
            }
        )
    except Exception:
        store.delete_files([path])
        raise

    try:
        _enqueue(document_id)
    except OperationalError as exc:
        logger.error("document %s could not be queued", document_id)
        store.delete_document(document_id)
        store.delete_files([path])
        raise _queue_unavailable() from exc
    return _to_response(store.get_document(document_id, user.id) or row)


@router.post("/portfolio", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentResponse)
def add_portfolio_link(user: User, body: PortfolioLinkRequest) -> DocumentResponse:
    try:
        url = portfolio.normalize_link(body.url)
    except portfolio.RejectedLink as exc:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code, exc.message) from exc

    # LinkedIn forbids automated reading, so the address is kept as text and never fetched.
    if portfolio.is_linkedin(url):
        row = store.insert_document(
            {"user_id": user.id, "type": "portfolio_link", "url": url, "status": "ready"}
        )
        return _to_response(row)

    row = store.insert_document({"user_id": user.id, "type": "portfolio_link", "url": url})
    try:
        _enqueue(row["id"])
    except OperationalError as exc:
        logger.error("document %s could not be queued", row["id"])
        store.delete_document(row["id"])
        raise _queue_unavailable() from exc
    return _to_response(store.get_document(row["id"], user.id) or row)


@router.get("", response_model=list[DocumentResponse])
def list_documents(user: User) -> list[DocumentResponse]:
    return [_to_response(row) for row in store.list_documents(user.id)]


def _owned_document(document_id: UUID, user: CurrentUser) -> dict[str, Any]:
    row = store.get_document(str(document_id), user.id)
    if row is None:
        raise _error(status.HTTP_404_NOT_FOUND, "not_found", "Document not found.")
    return row


@router.get("/{document_id}/status", response_model=DocumentResponse)
def document_status(document_id: UUID, user: User) -> DocumentResponse:
    return _to_response(_owned_document(document_id, user))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, user: User) -> None:
    row = _owned_document(document_id, user)
    if row.get("file_path"):
        store.delete_files([row["file_path"]])
    store.delete_document(row["id"])
