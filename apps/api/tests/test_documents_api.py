from typing import Any

import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

from app.main import MAX_REQUEST_BYTES
from app.routers import documents
from tests import sample_files
from tests.helpers import OTHER_USER_ID, USER_ID, FakeStore, auth_headers


class FakeQueue:
    def __init__(self) -> None:
        self.queued: list[str] = []
        self.error: Exception | None = None

    def apply_async(self, args: list[str], retry: bool = True) -> None:
        if self.error:
            raise self.error
        self.queued.append(args[0])


@pytest.fixture
def queue(monkeypatch: pytest.MonkeyPatch) -> FakeQueue:
    fake = FakeQueue()
    monkeypatch.setattr(documents, "parse_document", fake)
    return fake


def upload(
    client: TestClient,
    data: bytes,
    name: str = "cv.pdf",
    doc_type: str = "resume",
    user_id: str = USER_ID,
) -> Any:
    return client.post(
        "/documents",
        headers=auth_headers(user_id),
        data={"type": doc_type},
        files={"file": (name, data, "application/octet-stream")},
    )


def test_upload_stores_file_and_queues_parsing(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    response = upload(client, sample_files.text_pdf())
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["fileName"] == "cv.pdf"
    assert queue.queued == [body["id"]]
    assert list(fake_store.files) == [f"{USER_ID}/{body['id']}.pdf"]


def test_upload_uses_content_not_extension_for_the_stored_type(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    body = upload(client, sample_files.sample_docx(), name="cv.pdf").json()
    assert list(fake_store.files) == [f"{USER_ID}/{body['id']}.docx"]


@pytest.mark.parametrize(
    ("data", "status", "code"),
    [
        (b"MZ\x90\x00 executable", 415, "unsupported_type"),
        (b"", 422, "empty_file"),
    ],
)
def test_rejected_upload_stores_nothing_and_explains_why(
    client: TestClient,
    fake_store: FakeStore,
    queue: FakeQueue,
    data: bytes,
    status: int,
    code: str,
) -> None:
    response = upload(client, data, name="resume.pdf")
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert response.json()["detail"]["message"]
    assert fake_store.files == {}
    assert fake_store.documents == {}
    assert queue.queued == []


def test_crafted_file_name_cannot_choose_the_path(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    body = upload(client, sample_files.text_pdf(), name="../../../evil.pdf").json()
    assert body["fileName"] == "evil.pdf"
    assert list(fake_store.files) == [f"{USER_ID}/{body['id']}.pdf"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("..\\..\\evil.pdf", "evil.pdf"),
        ("evil\x07\n.pdf", "evil.pdf"),
        ("", "document"),
        (None, "document"),
        ("a" * 500, "a" * 200),
        # Names from the mobile app arrive percent-encoded.
        ("CareerFit%20test%20resume.pdf", "CareerFit test resume.pdf"),
        ("%D0%A0%D0%B5%D0%B7%D1%8E%D0%BC%D0%B5.pdf", "Резюме.pdf"),
        ("SENECA%20(1).pdf", "SENECA (1).pdf"),
        ("..%2F..%2Fevil.pdf", "evil.pdf"),
        ("evil%07.pdf", "evil.pdf"),
        # Anything that isn't valid encoding is kept as it was sent.
        ("100% done.pdf", "100% done.pdf"),
        ("%FF%FE.pdf", "%FF%FE.pdf"),
    ],
)
def test_display_name_is_cleaned(raw: str | None, expected: str) -> None:
    assert documents._display_name(raw) == expected


def test_a_percent_encoded_upload_name_is_shown_readably(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    body = upload(client, sample_files.text_pdf(), name="%D0%A0%D0%B5%D0%B7%D1%8E%D0%BC%D0%B5%201.pdf").json()
    assert body["fileName"] == "Резюме 1.pdf"


def test_upload_requires_auth(client: TestClient, fake_store: FakeStore, queue: FakeQueue) -> None:
    response = client.post(
        "/documents",
        data={"type": "resume"},
        files={"file": ("cv.pdf", sample_files.text_pdf(), "application/pdf")},
    )
    assert response.status_code == 401
    assert fake_store.files == {}


def test_invalid_document_type_is_rejected(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    assert upload(client, sample_files.text_pdf(), doc_type="portfolio_link").status_code == 422


def test_oversized_request_is_refused_before_routing(client: TestClient) -> None:
    response = client.post(
        "/documents",
        headers={**auth_headers(), "Content-Type": "multipart/form-data; boundary=x"},
        content=b"x" * (MAX_REQUEST_BYTES + 1),
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "too_large"


def test_queue_outage_cleans_up_and_reports(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    queue.error = OperationalError("redis down")
    response = upload(client, sample_files.text_pdf())
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "processing_unavailable"
    assert fake_store.files == {}
    assert fake_store.documents == {}


def test_status_list_and_delete_flow(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    document_id = upload(client, sample_files.text_pdf()).json()["id"]
    fake_store.update_document(document_id, {"status": "failed", "error_code": "no_text"})

    status = client.get(f"/documents/{document_id}/status", headers=auth_headers()).json()
    assert status["status"] == "failed"
    assert status["errorCode"] == "no_text"
    assert status["errorMessage"]

    listed = client.get("/documents", headers=auth_headers()).json()
    assert [row["id"] for row in listed] == [document_id]

    assert client.delete(f"/documents/{document_id}", headers=auth_headers()).status_code == 204
    assert fake_store.files == {}
    assert fake_store.documents == {}


def test_other_users_cannot_reach_a_document(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    document_id = upload(client, sample_files.text_pdf()).json()["id"]
    other = auth_headers(OTHER_USER_ID)

    assert client.get(f"/documents/{document_id}/status", headers=other).status_code == 404
    assert client.delete(f"/documents/{document_id}", headers=other).status_code == 404
    assert client.get("/documents", headers=other).json() == []
    assert document_id in fake_store.documents
    assert len(fake_store.files) == 1


def test_document_id_must_be_a_uuid(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    response = client.get("/documents/eq.anything/status", headers=auth_headers())
    assert response.status_code == 422


def test_portfolio_link_is_queued(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    response = client.post(
        "/documents/portfolio", headers=auth_headers(), json={"url": "https://example.com/work"}
    )
    assert response.status_code == 202
    assert response.json()["url"] == "https://example.com/work"
    assert queue.queued == [response.json()["id"]]


def test_linkedin_is_kept_as_text_and_never_fetched(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue
) -> None:
    response = client.post(
        "/documents/portfolio",
        headers=auth_headers(),
        json={"url": "https://www.linkedin.com/in/someone"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "ready"
    assert queue.queued == []


@pytest.mark.parametrize(
    "url", ["http://169.254.169.254/latest/meta-data/", "file:///etc/passwd", "http://localhost/"]
)
def test_unsafe_portfolio_link_is_rejected(
    client: TestClient, fake_store: FakeStore, queue: FakeQueue, url: str
) -> None:
    response = client.post("/documents/portfolio", headers=auth_headers(), json={"url": url})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_link"
    assert fake_store.documents == {}
    assert queue.queued == []
