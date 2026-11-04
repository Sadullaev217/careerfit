import pytest

from app.file_validation import MAX_FILE_BYTES, MAX_PDF_PAGES, RejectedFile, validate_file
from tests import sample_files


def rejection(data: bytes) -> RejectedFile:
    with pytest.raises(RejectedFile) as caught:
        validate_file(data)
    return caught.value


def test_accepts_real_pdf() -> None:
    assert validate_file(sample_files.text_pdf()).name == "pdf"


def test_accepts_scanned_pdf() -> None:
    assert validate_file(sample_files.scanned_pdf()).name == "pdf"


def test_accepts_real_docx() -> None:
    assert validate_file(sample_files.sample_docx()).name == "docx"


@pytest.mark.parametrize(
    "data",
    [
        b"MZ\x90\x00 windows executable",
        b"<html><script>alert(1)</script></html>",
        b"just some text",
        b"\x89PNG\r\n\x1a\n image",
    ],
)
def test_rejects_other_types_by_content(data: bytes) -> None:
    assert rejection(data).code == "unsupported_type"


def test_rejects_plain_zip_posing_as_docx() -> None:
    assert rejection(sample_files.zip_with({"a.txt": b"hi"})).code == "unsupported_type"


def test_rejects_empty_file() -> None:
    assert rejection(b"").code == "empty_file"


def test_rejects_oversized_file() -> None:
    result = rejection(b"%PDF-" + b"0" * MAX_FILE_BYTES)
    assert (result.code, result.status_code) == ("too_large", 413)


def test_rejects_legacy_word_file() -> None:
    assert rejection(bytes.fromhex("D0CF11E0A1B11AE1") + b"0" * 64).code == "unsupported_word_format"


def test_rejects_damaged_pdf() -> None:
    assert rejection(b"%PDF-1.7 this is not really a pdf").code == "invalid_file"


def test_rejects_damaged_docx() -> None:
    assert rejection(b"PK\x03\x04 not really a zip").code == "invalid_file"


def test_rejects_password_protected_pdf() -> None:
    assert rejection(sample_files.encrypted_pdf()).code == "password_protected"


def test_rejects_too_many_pages() -> None:
    assert rejection(sample_files.text_pdf(pages=MAX_PDF_PAGES + 1)).code == "too_many_pages"


@pytest.mark.parametrize("marker", [b"/JavaScript", b"/JS ", b"/J#61vaScript", b"/Launch", b"/EmbeddedFile"])
def test_rejects_pdf_active_content(marker: bytes) -> None:
    assert rejection(sample_files.text_pdf() + b"\n" + marker).code == "unsafe_file"


@pytest.mark.parametrize(
    "entry",
    ["word/vbaProject.bin", "word/embeddings/oleObject1.bin", "word/activeX/activeX1.bin"],
)
def test_rejects_docx_active_content(entry: str) -> None:
    assert rejection(sample_files.docx_with({entry: b"x"})).code == "unsafe_file"


def test_rejects_zip_bomb() -> None:
    bomb = sample_files.docx_with({"word/media/huge.bin": b"\0" * (60 * 1024 * 1024)})
    assert len(bomb) < MAX_FILE_BYTES
    assert rejection(bomb).code == "unsafe_file"
