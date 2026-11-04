import json
import logging
import os
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

from app import embeddings, skill_matching, tasks
from app.extraction import ExtractionFailed
from app.llm import LLMUnavailable
from app.profile_schema import ExtractedProfile
from app.skill_matching import MIN_MATCH_SIMILARITY, match_names, profile_skill_rows
from app.tasks import extract_resume, parse_document
from scripts.seed_esco import START_URL, fetch_skills, to_rows
from tests import sample_files
from tests.helpers import OTHER_USER_ID, USER_ID, VALID_PROFILE, FakeStore, auth_headers


class FakeIndex:
    def __init__(self, rows: dict[float, dict[str, Any] | None]) -> None:
        self.rows = rows

    def match_skill(self, embedding: list[float]) -> dict[str, Any] | None:
        return self.rows.get(embedding[0])


def hit(skill_id: str, similarity: float = 0.9) -> dict[str, Any]:
    return {"id": skill_id, "name": f"canonical {skill_id}", "esco_id": f"esco/{skill_id}", "similarity": similarity}


def fake_embed(monkeypatch: pytest.MonkeyPatch, vectors: dict[str, float]) -> None:
    monkeypatch.setattr(
        skill_matching, "embed_texts", lambda names: [[vectors[name]] for name in names]
    )


def test_matches_above_the_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_embed(monkeypatch, {"Python": 1.0})
    match = match_names(["Python"], FakeIndex({1.0: hit("a")}))[0]
    assert match is not None
    assert (match.skill_id, match.esco_id) == ("a", "esco/a")


def test_weak_match_stays_unmapped(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_embed(monkeypatch, {"Odd": 1.0})
    weak = hit("a", MIN_MATCH_SIMILARITY - 0.01)
    assert match_names(["Odd"], FakeIndex({1.0: weak})) == [None]


def test_no_names_means_no_embedding_work(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_names: list[str]) -> list[list[float]]:
        raise AssertionError("should not embed")

    monkeypatch.setattr(skill_matching, "embed_texts", fail)
    assert match_names([], FakeIndex({})) == []


def test_rows_drop_unknown_level_and_unmapped_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_embed(monkeypatch, {"Python": 1.0, "SQL": 2.0})
    profile = ExtractedProfile.model_validate(VALID_PROFILE)
    rows = profile_skill_rows(profile, USER_ID, "doc-1", FakeIndex({1.0: hit("a"), 2.0: None}))
    assert len(rows) == 1
    assert rows[0]["skill_id"] == "a"
    assert rows[0]["level"] == "advanced"
    assert rows[0]["source_document_id"] == "doc-1"

    fake_embed(monkeypatch, {"Python": 1.0, "SQL": 2.0})
    rows = profile_skill_rows(profile, USER_ID, "doc-1", FakeIndex({1.0: None, 2.0: hit("b")}))
    assert rows[0]["level"] is None


def test_two_phrases_for_one_skill_keep_the_surest(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_embed(monkeypatch, {"Python": 1.0, "SQL": 2.0})
    profile = ExtractedProfile.model_validate(VALID_PROFILE)
    rows = profile_skill_rows(
        profile, USER_ID, "doc-1", FakeIndex({1.0: hit("a"), 2.0: hit("a")})
    )
    assert len(rows) == 1
    assert rows[0]["source_name"] == "Python"


class FakeLLM:
    model = "fake-model"

    def __init__(self, output: Any = None) -> None:
        self.output = output if output is not None else json.dumps(VALID_PROFILE)
        self.calls = 0

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str:
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return str(self.output)


def add_parsed_resume(store: FakeStore) -> str:
    store.insert_document(
        {
            "id": "doc-1",
            "user_id": USER_ID,
            "type": "resume",
            "file_path": f"{USER_ID}/doc-1.pdf",
            "status": "ready",
            "parsed_text": "resume text",
        }
    )
    return "doc-1"


@pytest.fixture
def embed_all(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_embed(monkeypatch, {"Python": 1.0, "SQL": 2.0})


def test_extraction_saves_profile_and_skills(
    fake_store: FakeStore, embed_all: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_parsed_resume(fake_store)
    fake_store.skill_matches = {"1.0": hit("a"), "2.0": hit("b")}
    monkeypatch.setattr(tasks, "get_llm", lambda: FakeLLM())
    extract_resume.apply(args=["doc-1"])

    row = fake_store.documents["doc-1"]
    assert row["extraction_status"] == "ready"
    saved = fake_store.saved_extractions["doc-1"]
    assert saved["model"] == "fake-model"
    assert saved["data"]["skills"][0]["name_en"] == "Python"
    assert {skill["skill_id"] for skill in fake_store.profile_skills} == {"a", "b"}


def test_invalid_model_output_records_failure(
    fake_store: FakeStore, embed_all: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_parsed_resume(fake_store)
    monkeypatch.setattr(tasks, "get_llm", lambda: FakeLLM("not json"))
    extract_resume.apply(args=["doc-1"])
    row = fake_store.documents["doc-1"]
    assert (row["extraction_status"], row["extraction_error"]) == ("failed", "invalid_model_output")
    assert row["status"] == "ready"
    assert "doc-1" not in fake_store.saved_extractions


def test_ai_outage_retries_then_fails_without_losing_the_parsed_resume(
    fake_store: FakeStore, embed_all: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_parsed_resume(fake_store)
    llm = FakeLLM(LLMUnavailable("down"))
    monkeypatch.setattr(tasks, "get_llm", lambda: llm)
    extract_resume.apply(args=["doc-1"])
    row = fake_store.documents["doc-1"]
    assert (row["extraction_status"], row["extraction_error"]) == ("failed", "ai_unavailable")
    assert row["parsed_text"] == "resume text"
    assert llm.calls == tasks.MAX_RETRIES + 1


def test_extraction_errors_never_log_resume_contents(
    fake_store: FakeStore,
    embed_all: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_parsed_resume(fake_store)

    def explode(*_args: object) -> Any:
        raise ValueError("RESUME-SENTINEL jane@example.com")

    monkeypatch.setattr(tasks, "extract_profile", explode)
    monkeypatch.setattr(tasks, "get_llm", lambda: FakeLLM())
    with caplog.at_level(logging.DEBUG):
        extract_resume.apply(args=["doc-1"])
    assert "RESUME-SENTINEL" not in caplog.text
    assert fake_store.documents["doc-1"]["extraction_error"] == "extraction_error"


def test_deleted_document_is_ignored(fake_store: FakeStore) -> None:
    extract_resume.apply(args=["missing"])
    assert fake_store.saved_extractions == {}


def test_known_extraction_failure_code_is_kept(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_parsed_resume(fake_store)

    def fail(*_args: object) -> Any:
        raise ExtractionFailed("invalid_model_output")

    monkeypatch.setattr(tasks, "extract_profile", fail)
    monkeypatch.setattr(tasks, "get_llm", lambda: FakeLLM())
    extract_resume.apply(args=["doc-1"])
    assert fake_store.documents["doc-1"]["extraction_error"] == "invalid_model_output"


class FakeExtractQueue:
    def __init__(self) -> None:
        self.queued: list[str] = []
        self.error: Exception | None = None

    def apply_async(self, args: list[str], retry: bool = True) -> None:
        if self.error:
            raise self.error
        self.queued.append(args[0])


def add_uploaded(store: FakeStore, doc_type: str) -> str:
    store.upload_file(f"{USER_ID}/doc.pdf", sample_files.text_pdf(), "application/pdf")
    store.insert_document(
        {"id": "doc-2", "user_id": USER_ID, "type": doc_type, "file_path": f"{USER_ID}/doc.pdf"}
    )
    return "doc-2"


def test_parsed_resume_is_queued_for_extraction(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = FakeExtractQueue()
    monkeypatch.setattr(tasks, "extract_resume", queue)
    parse_document.apply(args=[add_uploaded(fake_store, "resume")])
    assert queue.queued == ["doc-2"]
    assert fake_store.documents["doc-2"]["extraction_status"] == "pending"


def test_cover_letter_is_not_extracted(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = FakeExtractQueue()
    monkeypatch.setattr(tasks, "extract_resume", queue)
    parse_document.apply(args=[add_uploaded(fake_store, "cover_letter")])
    assert queue.queued == []
    assert fake_store.documents["doc-2"].get("extraction_status") is None


def test_queue_outage_keeps_the_parsed_resume(
    fake_store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    queue = FakeExtractQueue()
    queue.error = OperationalError("redis down")
    monkeypatch.setattr(tasks, "extract_resume", queue)
    parse_document.apply(args=[add_uploaded(fake_store, "resume")])
    row = fake_store.documents["doc-2"]
    assert row["status"] == "ready"
    assert (row["extraction_status"], row["extraction_error"]) == ("failed", "queue_unavailable")


def test_profile_endpoint_returns_only_the_owners_analysis(
    client: TestClient, fake_store: FakeStore
) -> None:
    document_id = "33333333-3333-3333-3333-333333333333"
    fake_store.save_extraction(document_id, USER_ID, VALID_PROFILE, "v1", "m", False, False, [])
    url = f"/documents/{document_id}/profile"

    owned = client.get(url, headers=auth_headers())
    assert owned.status_code == 200
    assert owned.json()["promptVersion"] == "v1"
    assert owned.json()["profile"]["seniority"] == "mid"

    assert client.get(url, headers=auth_headers(OTHER_USER_ID)).status_code == 404
    assert client.get(url).status_code == 401


def test_document_response_explains_extraction_failure(
    client: TestClient, fake_store: FakeStore
) -> None:
    fake_store.insert_document(
        {
            "id": "44444444-4444-4444-4444-444444444444",
            "user_id": USER_ID,
            "type": "resume",
            "extraction_status": "failed",
            "extraction_error": "ai_unavailable",
        }
    )
    body = client.get("/documents", headers=auth_headers()).json()[0]
    assert body["extractionStatus"] == "failed"
    assert body["extractionErrorMessage"]


def test_seed_rows_keep_one_concept_per_name() -> None:
    rows = to_rows(
        [
            {"uri": "esco/1", "title": "Weld", "preferredLabel": {"en": "weld"}},
            {"uri": "esco/2", "title": "Weld", "preferredLabel": {"en": "Weld"}},
            {"uri": "esco/3", "title": "Cook"},
        ]
    )
    assert rows == [{"name": "weld", "esco_id": "esco/1"}, {"name": "Cook", "esco_id": "esco/3"}]


def test_seed_follows_pages_and_refuses_other_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.seed_esco.PAGE_DELAY_SECONDS", 0)
    pages = {
        "0": {
            "_embedded": {"results": [{"uri": "a", "title": "A"}]},
            "_links": {"next": {"href": "https://ec.europa.eu/esco/api/search?page=1"}},
        },
        "1": {"_embedded": {"results": [{"uri": "b", "title": "B"}]}, "_links": {}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[request.url.params.get("page", "0")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        assert [row["uri"] for row in fetch_skills(http, None)] == ["a", "b"]

    evil = {
        "_embedded": {"results": []},
        "_links": {"next": {"href": "https://evil.example/x"}},
    }
    with httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(200, json=evil))) as http, pytest.raises(RuntimeError):
        list(fetch_skills(http, None))
    assert START_URL.startswith("https://ec.europa.eu/")


needs_embedding_model = pytest.mark.skipif(
    not os.environ.get("RUN_EMBEDDING_TESTS"), reason="RUN_EMBEDDING_TESTS not set"
)


@needs_embedding_model
def test_real_model_output_shape() -> None:
    vectors = embeddings.embed_texts(["welding", "бухгалтер"])
    assert len(vectors) == 2
    assert len(vectors[0]) == embeddings.EMBEDDING_DIMENSIONS


@needs_embedding_model
def test_real_model_separates_english_skills() -> None:
    import numpy as np

    def similarity(a: str, b: str) -> float:
        left, right = np.array(embeddings.embed_texts([a, b]))
        return float(left @ right / (np.linalg.norm(left) * np.linalg.norm(right)))

    assert similarity("React", "Vue.js") > similarity("React", "welding")
    assert similarity("bookkeeping", "accounting") > similarity("cooking", "contract law")
