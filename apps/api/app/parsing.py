import io
import re

import docx
import pdfplumber
import pypdfium2
import pytesseract
from docx.text.paragraph import Paragraph

from app.config import settings

MAX_TEXT_CHARS = 200_000
MAX_OCR_PAGES = 20
MIN_PAGE_TEXT_CHARS = 20
OCR_DPI = 300
OCR_PAGE_TIMEOUT_SECONDS = 60

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RUNS_OF_SPACES = re.compile(r"[ \t]+")
_RUNS_OF_BLANK_LINES = re.compile(r"\n{3,}")


class ParseFailure(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def clean_text(text: str, limit: int = MAX_TEXT_CHARS) -> str:
    # Postgres text columns reject NUL bytes, which some PDFs produce.
    text = _CONTROL_CHARS.sub("", text)
    text = _RUNS_OF_SPACES.sub(" ", text)
    text = _RUNS_OF_BLANK_LINES.sub("\n\n", text)
    return text.strip()[:limit]


def extract_text(data: bytes, kind: str) -> str:
    text = _extract_pdf(data) if kind == "pdf" else _extract_docx(data)
    if not text:
        raise ParseFailure("no_text")
    return text


def _extract_pdf(data: bytes) -> str:
    ocr_budget = MAX_OCR_PAGES
    ocr_unavailable = False
    pages: list[str] = []
    rendered = pypdfium2.PdfDocument(data)
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for index, page in enumerate(pdf.pages):
                text = (page.extract_text() or "").strip()
                if len(text) < MIN_PAGE_TEXT_CHARS and ocr_budget > 0 and not ocr_unavailable:
                    ocr_budget -= 1
                    try:
                        text = _ocr_page(rendered[index]) or text
                    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError):
                        ocr_unavailable = True
                pages.append(text)
    finally:
        rendered.close()

    text = clean_text("\n\n".join(page for page in pages if page))
    if not text and ocr_unavailable:
        raise ParseFailure("ocr_unavailable")
    return text


def _ocr_page(page: pypdfium2.PdfPage) -> str:
    image = page.render(scale=OCR_DPI / 72).to_pil()
    return str(
        pytesseract.image_to_string(
            image, lang=settings.ocr_languages, timeout=OCR_PAGE_TIMEOUT_SECONDS
        )
    ).strip()


def _extract_docx(data: bytes) -> str:
    document = docx.Document(io.BytesIO(data))
    parts: list[str] = []
    for section in document.sections:
        parts.extend(paragraph.text for paragraph in section.header.paragraphs)
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            parts.append(block.text)
        else:
            for row in block.rows:
                # Merged cells repeat once per spanned column.
                cells = dict.fromkeys(cell.text.strip() for cell in row.cells)
                parts.append(" | ".join(cell for cell in cells if cell))
    for section in document.sections:
        parts.extend(paragraph.text for paragraph in section.footer.paragraphs)

    unique = dict.fromkeys(part.strip() for part in parts if part.strip())
    return clean_text("\n".join(unique))
