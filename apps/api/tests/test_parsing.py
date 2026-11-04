import os
import shutil

import pytesseract
import pytest

from app.parsing import MAX_OCR_PAGES, ParseFailure, clean_text, extract_text
from tests import sample_files

needs_tesseract = pytest.mark.skipif(
    shutil.which("tesseract") is None and not os.environ.get("CI"),
    reason="tesseract not installed",
)


def test_extracts_text_pdf() -> None:
    assert "Senior accountant" in extract_text(sample_files.text_pdf(), "pdf")


def test_extracts_docx_body_tables_and_header() -> None:
    text = extract_text(sample_files.sample_docx(), "docx")
    assert "Registered nurse" in text
    assert "Skills | Triage and charting" in text
    assert "Jordan Lee" in text


@needs_tesseract
def test_extracts_scanned_pdf_with_real_ocr() -> None:
    assert "accountant" in extract_text(sample_files.scanned_pdf(), "pdf").lower()


def test_digital_pdf_does_not_use_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("OCR should not run on a digital PDF")

    monkeypatch.setattr(pytesseract, "image_to_string", fail)
    assert extract_text(sample_files.text_pdf(), "pdf")


def test_ocr_is_limited_to_a_page_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def fake_ocr(*_args: object, **_kwargs: object) -> str:
        calls.append(1)
        return "recognised page text from the scan"

    monkeypatch.setattr(pytesseract, "image_to_string", fake_ocr)
    assert extract_text(sample_files.scanned_pdf(text=None, pages=MAX_OCR_PAGES + 3), "pdf")
    assert len(calls) == MAX_OCR_PAGES


def test_blank_scan_reports_no_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *_a, **_k: "  ")
    with pytest.raises(ParseFailure) as caught:
        extract_text(sample_files.scanned_pdf(text=None), "pdf")
    assert caught.value.code == "no_text"


def test_missing_tesseract_is_reported_on_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*_args: object, **_kwargs: object) -> str:
        raise pytesseract.TesseractNotFoundError()

    monkeypatch.setattr(pytesseract, "image_to_string", missing)
    with pytest.raises(ParseFailure) as caught:
        extract_text(sample_files.scanned_pdf(), "pdf")
    assert caught.value.code == "ocr_unavailable"


def test_clean_text_removes_nul_bytes_postgres_rejects() -> None:
    assert clean_text("a\x00b\x07c  d\n\n\n\ne") == "abc d\n\ne"


def test_clean_text_applies_limit() -> None:
    assert len(clean_text("x" * 500, limit=100)) == 100
