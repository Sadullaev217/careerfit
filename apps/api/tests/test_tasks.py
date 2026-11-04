import logging
import os
import time

import httpx
import pytest
from celery.contrib.testing.worker import start_worker

from app import tasks
from app.celery_app import celery_app
from app.parsing import ParseFailure
from app.portfolio import LinkFetchFailed
from app.tasks import parse_document
from tests import sample_files
from tests.helpers import USER_ID, FakeStore

REDIS_URL = os.environ.get("TEST_REDIS_URL")


def add_file(store: FakeStore, data: bytes, extension: str = "pdf") -> str:
    path = f"{USER_ID}/doc.{extension}"
    store.upload_file(path, data, "application/octet-stream")
    return str(
        store.insert_document(
            {"id": "doc-1", "user_id": USER_ID, "type": "resume", "file_path": path}
        )["id"]
    )


def test_stores_parsed_text_from_pdf(fake_store: FakeStore) -> None:
    document_id = add_file(fake_store, sample_files.text_pdf())
    parse_document.apply(args=[document_id])
    row = fake_store.documents[document_id]
    assert row["status"] == "ready"
    assert "Senior accountant" in row["parsed_text"]


def test_stores_parsed_text_from_docx(fake_store: FakeStore) -> None:
    document_id = add_file(fake_store, sample_files.sample_docx(), "docx")
    parse_document.apply(args=[document_id])
    assert "Registered nurse" in fake_store.documents[document_id]["parsed_text"]


def test_records_known_failures(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    document_id = add_file(fake_store, sample_files.text_pdf())

    def fail(*_args: object) -> str:
        raise ParseFailure("no_text")

    monkeypatch.setattr(tasks, "extract_text", fail)
    parse_document.apply(args=[document_id])
    row = fake_store.documents[document_id]
    assert (row["status"], row["error_code"]) == ("failed", "no_text")


def test_unexpected_error_never_logs_resume_contents(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    document_id = add_file(fake_store, sample_files.text_pdf())

    def fail(*_args: object) -> str:
        raise ValueError("RESUME-SENTINEL jane@example.com")

    monkeypatch.setattr(tasks, "extract_text", fail)
    with caplog.at_level(logging.DEBUG):
        parse_document.apply(args=[document_id])

    assert fake_store.documents[document_id]["error_code"] == "parse_error"
    assert "RESUME-SENTINEL" not in caplog.text
    assert "ValueError" in caplog.text


def test_network_errors_retry_then_fail(fake_store: FakeStore) -> None:
    document_id = add_file(fake_store, sample_files.text_pdf())
    fake_store.download_error = httpx.ConnectTimeout("slow")
    parse_document.apply(args=[document_id])
    row = fake_store.documents[document_id]
    assert (row["status"], row["error_code"]) == ("failed", "network_error")
    assert fake_store.download_calls == tasks.MAX_RETRIES + 1


def test_document_deleted_before_processing_is_ignored(fake_store: FakeStore) -> None:
    parse_document.apply(args=["missing"])
    assert fake_store.documents == {}


def test_portfolio_link_text_is_stored(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_store.insert_document(
        {"id": "link-1", "user_id": USER_ID, "type": "portfolio_link", "url": "https://a.example/"}
    )
    monkeypatch.setattr(tasks.portfolio, "read_link", lambda _url: "Rebuilt billing")
    parse_document.apply(args=["link-1"])
    assert fake_store.documents["link-1"]["parsed_text"] == "Rebuilt billing"


def test_portfolio_failure_is_recorded(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_store.insert_document(
        {"id": "link-1", "user_id": USER_ID, "type": "portfolio_link", "url": "https://a.example/"}
    )

    def fail(_url: str) -> str:
        raise LinkFetchFailed("link_blocked")

    monkeypatch.setattr(tasks.portfolio, "read_link", fail)
    parse_document.apply(args=["link-1"])
    assert fake_store.documents["link-1"]["error_code"] == "link_blocked"


def test_empty_portfolio_page_is_reported(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_store.insert_document(
        {"id": "link-1", "user_id": USER_ID, "type": "portfolio_link", "url": "https://a.example/"}
    )
    monkeypatch.setattr(tasks.portfolio, "read_link", lambda _url: "")
    parse_document.apply(args=["link-1"])
    assert fake_store.documents["link-1"]["error_code"] == "no_text"


@pytest.mark.skipif(not REDIS_URL, reason="TEST_REDIS_URL not set")
def test_real_worker_processes_a_queued_document(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(celery_app.conf, "broker_url", REDIS_URL)
    document_id = add_file(fake_store, sample_files.text_pdf())

    with start_worker(celery_app, pool="solo", perform_ping_check=False, loglevel="ERROR"):
        parse_document.apply_async(args=[document_id], retry=False)
        deadline = time.monotonic() + 30
        while (
            fake_store.documents[document_id]["status"] != "ready" and time.monotonic() < deadline
        ):
            time.sleep(0.2)

    assert fake_store.documents[document_id]["status"] == "ready"
