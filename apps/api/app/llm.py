"""The only module that talks to an AI provider. A new provider is one more class here."""

from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config import settings

# Ollama silently cuts off input beyond its default window, so the size is set explicitly.
OLLAMA_CONTEXT_TOKENS = 16384
OLLAMA_MAX_OUTPUT_TOKENS = 4096
RETRY_TEMPERATURE = 0.2


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


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaClient(settings.ollama_url, settings.llm_model, settings.llm_timeout_seconds)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
