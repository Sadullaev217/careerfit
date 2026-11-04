import logging
from typing import Any

import httpx
from celery.exceptions import SoftTimeLimitExceeded

from app import portfolio, store
from app.celery_app import celery_app
from app.parsing import ParseFailure, extract_text

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
