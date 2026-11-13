"""Everything CareerFit holds about one person, as a zip they can download (GDPR access and portability).

data.json has every row from every table that holds their data (store.USER_TABLES and
store.DOCUMENT_TABLES); files/ has the files they uploaded that are still stored.
"""

import io
import json
import re
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

README = """CareerFit: your data

data.json      Everything stored about you, one list per database table: your account, agreements,
               documents and the text read from them, the skills and history found in them, analyses
               and their reports, tailored lines, purchases and notification devices.
files/         The files you uploaded that are still stored. Files are deleted 90 days after upload
               unless you chose to keep them.

Payment details are held by Stripe, Apple or Google, never by CareerFit.
To delete everything, use Settings > Delete my account.
"""

_UNSAFE_NAME = re.compile(r"[^\w.\- ]+")


def _file_name(document: dict[str, Any]) -> str:
    path = str(document.get("file_path") or "")
    extension = path.rsplit(".", 1)[-1] if "." in path else "bin"
    stem = _UNSAFE_NAME.sub("_", str(document.get("file_name") or "file")).strip(" ._")[:80] or "file"
    if not stem.lower().endswith(f".{extension}"):
        stem = f"{stem}.{extension}"
    return f"files/{document['id']}-{stem}"


def build_zip(
    account: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
    download: Callable[[str], bytes],
    now: datetime | None = None,
) -> bytes:
    missing: list[str] = []
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", README)
        for document in tables.get("documents", []):
            path = document.get("file_path")
            if not path:
                continue
            try:
                archive.writestr(_file_name(document), download(str(path)))
            except httpx.HTTPStatusError:
                missing.append(str(document["id"]))
        body = {
            "exported_at": (now or datetime.now(UTC)).isoformat(),
            "account": account,
            "tables": tables,
            "documents_whose_file_could_not_be_read": missing,
        }
        archive.writestr("data.json", json.dumps(body, ensure_ascii=False, indent=2, default=str))
    return buffer.getvalue()
