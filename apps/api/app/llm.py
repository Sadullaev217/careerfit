"""The only module that talks to an AI provider. A new provider is one more class here."""

import json
import logging
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Ollama silently cuts off input beyond its default window, so the size is set explicitly. It has to
# hold the largest input plus the longest answer. On qwen3.5:4b, a Russian resume at the extraction cap
# measured 11,015 tokens with its instructions. A master resume with 14 projects needed a 4,145-token
# answer, so the old limit of 4,096 cut it off mid-way and every retry failed the same way.
LARGEST_INPUT_TOKENS = 11_100
OLLAMA_MAX_OUTPUT_TOKENS = 8192
OLLAMA_CONTEXT_TOKENS = 20480
RETRY_TEMPERATURE = 0.2
# Some OpenRouter models always reason before answering, and that reasoning counts against this limit.
# A high effort can take most of a small limit and cut the answer off, so the limit is generous.
OPENROUTER_MAX_OUTPUT_TOKENS = 32_768


class LLMUnavailable(Exception):
    pass


class LLMClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str: ...


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self._model = model
        # trust_env is off so resume text can't be routed through a system proxy.
        self._http = httpx.Client(base_url=base_url, timeout=timeout_seconds, trust_env=False)

    @property
    def model(self) -> str:
        return self._model

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str:
        try:
            response = self._http.post(
                "/api/chat",
                json={
                    "model": self._model,
                    "stream": False,
                    "think": False,
                    "format": schema,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "options": {
                        # A retry at temperature 0 would just repeat the same bad answer.
                        "temperature": 0 if attempt == 0 else RETRY_TEMPERATURE,
                        "seed": attempt,
                        "num_ctx": OLLAMA_CONTEXT_TOKENS,
                        "num_predict": OLLAMA_MAX_OUTPUT_TOKENS,
                    },
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailable(type(exc).__name__) from exc
        content: str = response.json()["message"]["content"]
        return content


class OpenRouterClient:
    """A hosted model through OpenRouter. Resume text leaves the machine, so routing is limited to
    providers that, by OpenRouter's records, don't collect or train on prompts."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float) -> None:
        self._model = model
        # trust_env is off so resume text can't be routed through a system proxy.
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
            trust_env=False,
        )

    @property
    def model(self) -> str:
        return self._model

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str:
        try:
            response = self._http.post(
                "/chat/completions",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0 if attempt == 0 else RETRY_TEMPERATURE,
                    "max_tokens": OPENROUTER_MAX_OUTPUT_TOKENS,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": "answer", "strict": True, "schema": schema},
                    },
                    # Reasoning, where a model does it, isn't needed in the answer.
                    "reasoning": {"exclude": True},
                    "provider": {"data_collection": "deny", "require_parameters": True},
                },
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMUnavailable(_failure(exc)) from exc
        if "error" in body or not body.get("choices"):
            code = (body.get("error") or {}).get("code", "no_choices")
            raise LLMUnavailable(f"openrouter_{code}")
        # An answer cut off by the limit comes back empty or partial; callers treat it as invalid.
        content: str = body["choices"][0]["message"].get("content") or ""
        return content


def _failure(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


class FallbackClient:
    """Asks the hosted model first and the local one when it fails, for example after the daily free
    limit. One is made per job, so `model` names the weaker model whenever it answered in that job."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self._primary = primary
        self._fallback = fallback
        self._used_fallback = False

    @property
    def model(self) -> str:
        return self._fallback.model if self._used_fallback else self._primary.model

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str:
        try:
            return self._primary.complete_json(system, user, schema, attempt)
        except LLMUnavailable as exc:
            logger.warning(
                "%s unavailable (%s), using %s", self._primary.model, exc, self._fallback.model
            )
        self._used_fallback = True
        return self._fallback.complete_json(system, user, schema, attempt)


DEMO_PROFILE: dict[str, Any] = {
    "skills": [
        {"name": "Python", "name_en": "Python", "level": "advanced", "years": 4, "confidence": 1},
        {"name": "SQL", "name_en": "SQL", "level": "intermediate", "years": 3, "confidence": 1},
    ],
    "work_history": [
        {
            "title": "Software Developer",
            "title_en": "Software Developer",
            "employer": "Example Co",
            "start_date": "2021-01",
            "end_date": None,
            "is_current": True,
            "confidence": 1,
        }
    ],
    "education": [],
    "certifications": [],
    "languages": [{"name_en": "English", "level": "native", "confidence": 1}],
    "projects": [],
    "industry_en": "Software",
    "industry_confidence": 1,
    "seniority": "mid",
    "seniority_confidence": 1,
    "flags": [],
}


def _smallest_answer(schema: dict[str, Any]) -> Any:
    kind = schema.get("type")
    if isinstance(kind, list):
        if "null" in kind:
            return None
        kind = kind[0]
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object":
        properties = schema.get("properties", {})
        return {key: _smallest_answer(properties[key]) for key in schema.get("required", [])}
    return {"array": [], "string": "", "integer": 0, "number": 0, "boolean": False}.get(
        str(kind)
    )


class DemoClient:
    """Fixed answers without any model, for the end-to-end tests and for trying the app without
    Ollama. Every resume reads as the same made-up developer. Deployed servers refuse it."""

    model = "demo"

    def complete_json(
        self, system: str, user: str, schema: dict[str, Any], attempt: int = 0
    ) -> str:
        if "work_history" in schema.get("properties", {}):
            return json.dumps(DEMO_PROFILE)
        return json.dumps(_smallest_answer(schema))


@lru_cache(maxsize=1)
def _ollama() -> OllamaClient:
    return OllamaClient(settings.ollama_url, settings.llm_model, settings.llm_timeout_seconds)


@lru_cache(maxsize=1)
def _openrouter() -> OpenRouterClient:
    return OpenRouterClient(
        settings.openrouter_url,
        settings.openrouter_api_key,
        settings.openrouter_model,
        settings.llm_timeout_seconds,
    )


def get_llm() -> LLMClient:
    """The model for one job. Not cached itself, because a fallback client remembers what it used."""
    if settings.llm_provider == "ollama":
        return _ollama()
    if settings.llm_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("LLM_PROVIDER is openrouter but OPENROUTER_API_KEY is empty")
        if settings.ollama_fallback:
            return FallbackClient(_openrouter(), _ollama())
        return _openrouter()
    if settings.llm_provider == "demo":
        return DemoClient()
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
