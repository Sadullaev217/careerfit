"""The agreement people accept before CareerFit reads their resume."""

import pytest
from fastapi.testclient import TestClient

from app import consent
from app.config import settings
from app.routers import analyses, documents
from tests import sample_files
from tests.helpers import USER_ID, FakeStore, auth_headers

SELF_HOSTED = "2026-11-24.self_hosted"


class _Queue:
    def apply_async(self, args: list[str], retry: bool = True) -> None:
        pass


@pytest.fixture
def new_person(fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    monkeypatch.setattr(analyses, "store", fake_store)
    monkeypatch.setattr(documents, "parse_document", _Queue())
    fake_store.consent_missing.add(USER_ID)
    return fake_store


def status_of(client: TestClient) -> dict[str, object]:
    response = client.get("/account/consent", headers=auth_headers())
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def upload(client: TestClient) -> int:
    return client.post(
        "/documents",
        headers=auth_headers(),
        data={"type": "resume"},
        files={"file": ("cv.pdf", sample_files.text_pdf(), "application/pdf")},
    ).status_code


def test_a_new_person_is_asked_first(client: TestClient, new_person: FakeStore) -> None:
    assert status_of(client) == {
        "version": SELF_HOSTED,
        "accepted": False,
        "acceptedAt": None,
        "aiProcessing": "self_hosted",
    }


def test_nothing_is_read_before_the_agreement(client: TestClient, new_person: FakeStore) -> None:
    refused = client.post(
        "/documents",
        headers=auth_headers(),
        data={"type": "resume"},
        files={"file": ("cv.pdf", sample_files.text_pdf(), "application/pdf")},
    )
    assert refused.status_code == 403
    assert refused.json()["detail"]["code"] == "consent_required"
    assert new_person.files == {}
    link = client.post(
        "/documents/portfolio", headers=auth_headers(), json={"url": "https://github.com/someone"}
    )
    assert link.status_code == 403
    analysis = client.post(
        "/analyses",
        headers=auth_headers(),
        json={"documentId": "3f2b8c1e-9a4d-4c55-8e21-0b7f6a1d2c3e", "role": "nurse"},
    )
    assert analysis.status_code == 403
    assert new_person.documents == {}


def test_reading_and_deleting_never_need_the_agreement(
    client: TestClient, new_person: FakeStore
) -> None:
    assert client.get("/documents", headers=auth_headers()).status_code == 200
    assert client.get("/account/plan", headers=auth_headers()).status_code == 200


def test_accepting_the_shown_version_unlocks_uploads(
    client: TestClient, new_person: FakeStore
) -> None:
    response = client.post(
        "/account/consent", headers=auth_headers(), json={"version": SELF_HOSTED}
    )
    assert response.status_code == 204
    after = status_of(client)
    assert after["accepted"] is True
    assert after["acceptedAt"]
    assert upload(client) == 202


def test_an_outdated_version_is_refused(client: TestClient, new_person: FakeStore) -> None:
    response = client.post(
        "/account/consent", headers=auth_headers(), json={"version": "2020-01-01.self_hosted"}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "consent_outdated"
    assert status_of(client)["accepted"] is False


def test_withdrawing_stops_new_processing_and_can_be_undone(
    client: TestClient, new_person: FakeStore
) -> None:
    client.post("/account/consent", headers=auth_headers(), json={"version": SELF_HOSTED})
    assert client.delete("/account/consent", headers=auth_headers()).status_code == 204
    assert status_of(client)["accepted"] is False
    assert new_person.consents[USER_ID, SELF_HOSTED]["withdrawn_at"]
    assert upload(client) == 403
    client.post("/account/consent", headers=auth_headers(), json={"version": SELF_HOSTED})
    assert upload(client) == 202


def test_switching_to_a_hosted_model_asks_again(
    client: TestClient, new_person: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post("/account/consent", headers=auth_headers(), json={"version": SELF_HOSTED})
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    status = status_of(client)
    assert status["version"] == "2026-11-24.openrouter"
    assert status["aiProcessing"] == "openrouter"
    assert status["accepted"] is False
    assert upload(client) == 403


def test_the_version_names_the_policy_date() -> None:
    assert consent.current_version().startswith(consent.POLICY_DATE)
