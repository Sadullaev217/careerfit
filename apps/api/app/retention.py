"""Deletes uploaded files 90 days after upload, unless the person chose to keep them.

The stored file, its extracted text and its search embedding go. The skills and history read from it,
and the results, stay until the person deletes them, so past results still open. Portfolio links aren't
uploads and aren't affected. A daily Celery beat job runs this.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

RETENTION_DAYS = 90
BATCH_SIZE = 100
# A run stops after this many batches, so a store that doesn't record the deletion can't loop forever.
MAX_BATCHES = 50


class RetentionStore(Protocol):
    def documents_to_expire(self, cutoff: datetime, limit: int) -> list[dict[str, Any]]: ...

    def delete_files(self, paths: list[str]) -> None: ...

    def expire_document(self, document_id: str, at: datetime) -> None: ...


def _created(row: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))


def delete_after(row: dict[str, Any]) -> str | None:
    """When this document's file will be deleted, or None if it won't be (kept, gone, or a link)."""
    if row.get("type") == "portfolio_link" or row.get("keep") or row.get("file_deleted_at"):
        return None
    return (_created(row) + timedelta(days=RETENTION_DAYS)).isoformat()


def delete_expired_files(store: RetentionStore, now: datetime | None = None) -> int:
    """Deletes every file past its 90 days. Returns how many documents lost their file."""
    moment = now or datetime.now(UTC)
    cutoff = moment - timedelta(days=RETENTION_DAYS)
    expired = 0
    for _ in range(MAX_BATCHES):
        rows = store.documents_to_expire(cutoff, BATCH_SIZE)
        if not rows:
            break
        paths = [str(row["file_path"]) for row in rows if row.get("file_path")]
        # Files go first: if that fails, the rows still point at them and the next run tries again.
        if paths:
            store.delete_files(paths)
        for row in rows:
            store.expire_document(str(row["id"]), moment)
        expired += len(rows)
    return expired
