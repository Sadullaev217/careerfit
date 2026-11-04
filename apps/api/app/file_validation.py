import io
import re
import zipfile
from dataclasses import dataclass

import pypdfium2

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 50
MAX_DOCX_ENTRIES = 1000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

_OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
_PDF_NAME_ESCAPE = re.compile(rb"#([0-9a-fA-F]{2})")
_PDF_ACTIVE_CONTENT = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia)\b")


class RejectedFile(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class FileKind:
    name: str
    extension: str
    content_type: str


PDF = FileKind("pdf", "pdf", "application/pdf")
DOCX = FileKind(
    "docx",
    "docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
KINDS_BY_EXTENSION = {PDF.extension: PDF, DOCX.extension: DOCX}


def validate_file(data: bytes) -> FileKind:
    """Decides the type from the bytes alone, so a renamed file can't get through."""
    if not data:
        raise RejectedFile("empty_file", "This file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise RejectedFile("too_large", "This file is larger than the 10 MB limit.", 413)
    if data.startswith(b"%PDF-"):
        _validate_pdf(data)
        return PDF
    if data.startswith(b"PK\x03\x04"):
        _validate_docx(data)
        return DOCX
    if data.startswith(_OLE_MAGIC):
        raise RejectedFile(
            "unsupported_word_format",
            "Old .doc and password-protected Word files aren't supported. Save it as .docx or PDF.",
            415,
        )
    raise RejectedFile("unsupported_type", "Only PDF and DOCX files are supported.", 415)


def _validate_pdf(data: bytes) -> None:
    # A first layer only: active content inside compressed streams needs the Part 11 malware scan.
    unescaped = _PDF_NAME_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), data)
    if _PDF_ACTIVE_CONTENT.search(unescaped):
        raise RejectedFile(
            "unsafe_file",
            "This PDF contains scripts or embedded files. Export a plain PDF and try again.",
        )
    try:
        document = pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as exc:
        if "password" in str(exc).lower():
            raise RejectedFile(
                "password_protected",
                "This PDF is password protected. Remove the password and try again.",
            ) from exc
        raise RejectedFile("invalid_file", "This PDF is damaged and can't be read.") from exc
    try:
        if len(document) > MAX_PDF_PAGES:
            raise RejectedFile(
                "too_many_pages", f"This PDF has more than {MAX_PDF_PAGES} pages."
            )
    finally:
        document.close()


def _validate_docx(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
    except zipfile.BadZipFile as exc:
        raise RejectedFile("invalid_file", "This file is damaged and can't be read.") from exc

    names = {entry.filename.lower() for entry in entries}
    if "[content_types].xml" not in names or "word/document.xml" not in names:
        raise RejectedFile("unsupported_type", "Only PDF and DOCX files are supported.", 415)
    if any(
        name.endswith("vbaproject.bin") or "/embeddings/" in name or "/activex/" in name
        for name in names
    ):
        raise RejectedFile(
            "unsafe_file",
            "This document contains macros or embedded objects. Save a plain .docx and try again.",
        )
    if (
        len(entries) > MAX_DOCX_ENTRIES
        or sum(entry.file_size for entry in entries) > MAX_DOCX_UNCOMPRESSED_BYTES
    ):
        raise RejectedFile("unsafe_file", "This document is too large once unpacked.")
    if any(entry.flag_bits & 0x1 for entry in entries):
        raise RejectedFile(
            "password_protected",
            "This document is password protected. Remove the password and try again.",
        )
