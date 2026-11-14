"""The hosted model through OpenRouter, the fallback to the local model, and choosing between them."""

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from app import analysis
from app import llm as llm_module
from app.config import settings
from app.llm import (
    FallbackClient,
    LLMUnavailable,
    OllamaClient,
    OpenRouterClient,
    get_llm,
)
from app.profile_schema import ExtractedProfile
from app.skill_judgement import judgement_key
from tests.helpers import VALID_PROFILE

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}


def openrouter(handler: Any) -> OpenRouterClient:
    client = OpenRouterClient("http://openrouter.test/api/v1", "test-key", "vendor/model:free", 5)
    client._http = httpx.Client(
        base_url="http://openrouter.test/api/v1",
        headers={"Authorization": "Bearer test-key"},
        transport=httpx.MockTransport(handler),
    )
    return client


def answer(content: str | None) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_openrouter_request_asks_for_json_and_no_data_collection() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answer('{"ok": true}')

    assert openrouter(handler).complete_json("system text", "user text", SCHEMA) == '{"ok": true}'
    request = seen[0]
    body = json.loads(request.content)
    assert request.url.path == "/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert body["model"] == "vendor/model:free"
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert body["temperature"] == 0
    assert body["max_tokens"] == llm_module.OPENROUTER_MAX_OUTPUT_TOKENS
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "answer", "strict": True, "schema": SCHEMA},
    }
    # Providers that may keep or train on prompts are never used, and none may ignore the schema.
    assert body["provider"] == {"data_collection": "deny", "require_parameters": True}
    assert body["reasoning"] == {"exclude": True}
    # Some free models don't take a seed, and require_parameters would then rule them out.
    assert "seed" not in body


def test_openrouter_retry_raises_the_temperature() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return answer("{}")

    openrouter(handler).complete_json("s", "u", SCHEMA, attempt=1)
    assert seen[0]["temperature"] == llm_module.RETRY_TEMPERATURE


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            httpx.Response(429, json={"error": {"code": 429, "message": "Rate limit exceeded"}}),
            "HTTP 429",
        ),
        (httpx.Response(503, text="busy"), "HTTP 503"),
        (
            httpx.Response(200, json={"error": {"code": 502, "message": "provider down"}}),
            "openrouter_502",
        ),
        (httpx.Response(200, json={"choices": []}), "openrouter_no_choices"),
        (httpx.Response(200, text="not json"), "JSONDecodeError"),
    ],
)
def test_openrouter_failures_become_unavailable(response: httpx.Response, reason: str) -> None:
    with pytest.raises(LLMUnavailable, match=reason):
        openrouter(lambda _request: response).complete_json("s", "u", SCHEMA)


def test_openrouter_network_failure_becomes_unavailable() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMUnavailable, match="ConnectError"):
        openrouter(handler).complete_json("s", "u", SCHEMA)


def test_an_answer_without_content_is_empty_so_callers_retry() -> None:
    # A model that spends the whole limit reasoning returns no content at all.
    assert openrouter(lambda _request: answer(None)).complete_json("s", "u", SCHEMA) == ""


class FakeModel:
    def __init__(self, name: str, reply: str | None) -> None:
        self.model = name
        self.reply = reply
        self.calls = 0

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str:
        self.calls += 1
        if self.reply is None:
            raise LLMUnavailable("HTTP 429")
        return self.reply


def test_fallback_uses_the_hosted_model_while_it_works() -> None:
    hosted, local = FakeModel("hosted", "from hosted"), FakeModel("local", "from local")
    client = FallbackClient(hosted, local)
    assert client.complete_json("s", "u", SCHEMA) == "from hosted"
    assert client.model == "hosted"
    assert local.calls == 0


def test_fallback_switches_to_the_local_model_and_says_so() -> None:
    hosted, local = FakeModel("hosted", None), FakeModel("local", "from local")
    client = FallbackClient(hosted, local)
    assert client.complete_json("s", "u", SCHEMA) == "from local"
    # Once the local model has answered in a job, the job is recorded as the local model's.
    hosted.reply = "from hosted"
    client.complete_json("s", "u", SCHEMA)
    assert client.model == "local"


def test_fallback_failure_is_still_unavailable() -> None:
    client = FallbackClient(FakeModel("hosted", None), FakeModel("local", None))
    with pytest.raises(LLMUnavailable):
        client.complete_json("s", "u", SCHEMA)


def test_ollama_stays_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(get_llm(), OllamaClient)


def test_openrouter_needs_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        get_llm()


def test_openrouter_falls_back_to_ollama_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    llm_module._openrouter.cache_clear()
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    first, second = get_llm(), get_llm()
    assert isinstance(first, FallbackClient)
    # Each job gets its own client, so one job's fallback isn't reported for another.
    assert first is not second
    monkeypatch.setattr(settings, "ollama_fallback", False)
    assert isinstance(get_llm(), OpenRouterClient)
    llm_module._openrouter.cache_clear()


def test_a_judgement_is_saved_under_the_model_that_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, dict[str, Any]] = {}

    class Store:
        def get_skill_judgement(self, _document_id: str, key: str) -> dict[str, Any] | None:
            return saved.get(key)

        def save_skill_judgement(self, _document_id: str, key: str, result: dict[str, Any]) -> None:
            saved[key] = result

    llm = FallbackClient(FakeModel("hosted", None), FakeModel("local", "{}"))

    def judge(*_args: Any) -> SimpleNamespace:
        llm.complete_json("s", "u", SCHEMA)
        return SimpleNamespace(
            required=[], preferred=[], relevant_job_indexes=[], relevant_credential_indexes=[]
        )

    monkeypatch.setattr(analysis, "judge_skills", judge)
    profile = ExtractedProfile.model_validate(VALID_PROFILE)
    args = (profile, "Data analyst", ["SQL"], ["Python"])
    analysis._judgements(args[0], "doc-1", *args[1:], Store(), llm, lambda texts: [])  # type: ignore[arg-type]
    assert list(saved) == [judgement_key(*args, "local")]
    assert judgement_key(*args, "hosted") not in saved


def test_the_demo_model_reads_every_resume_as_the_same_made_up_developer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.extraction import extract_profile

    monkeypatch.setattr(settings, "llm_provider", "demo")
    result = extract_profile("Any resume text at all, long enough to read.", get_llm())
    assert [skill.name_en for skill in result.profile.skills] == ["Python", "SQL"]


def test_the_demo_model_gives_the_smallest_valid_answer_to_other_questions() -> None:
    schema = {
        "type": "object",
        "properties": {
            "rows": {"type": "array"},
            "level": {"type": "string", "enum": ["yes", "no"]},
            "note": {"type": ["string", "null"]},
            "extra": {"type": "string"},
        },
        "required": ["rows", "level", "note"],
    }
    assert json.loads(llm_module.DemoClient().complete_json("", "", schema)) == {
        "rows": [],
        "level": "yes",
        "note": None,
    }
