"""Personal data stays out of logs and error reports."""

import io
import json
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

from app import privacy_logging
from app.privacy_logging import REMOVED, RedactingFilter, redact, scrub_breadcrumb, scrub_event

API_DIR = Path(__file__).resolve().parents[1]
# Made-up values, assembled here so the repository's secret scan doesn't mistake them for real ones.
FAKE_JWT = "eyJ" + "hbGciOiJFUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJl"
FAKE_SUPABASE_KEY = "sb_" + "secret_abcdef"


@pytest.mark.parametrize(
    ("text", "hidden", "shown"),
    [
        ("sent to jane.doe+cv@example.co.uk today", "jane.doe", "[email]"),
        ("call +1 416-555-0199 now", "555", "[phone]"),
        ("call (416) 555-0199 now", "555", "[phone]"),
        ("call 416-555-0199 now", "555", "[phone]"),
        ("token " + FAKE_JWT + " here", "eyJ", "[token]"),
        ("Authorization: Bearer abc.def-ghi", "abc.def", "Bearer [token]"),
        ("key sk_test_51Habcdef and whsec_abc123", "sk_test_51", "[secret]"),
        ("key sk-or-v1-abcdef123 used", "abcdef123", "[secret]"),
        ("key " + FAKE_SUPABASE_KEY + " used", "abcdef", "[secret]"),
        ("DELETE /push-tokens/ExponentPushToken[xxxxABCD] 204", "xxxxABCD", "ExponentPushToken[…]"),
        ('203.0.113.77:51234 - "GET /me HTTP/1.1" 200', "113.77", "203.0.113.0"),
        ("from 2001:db8:85a3:8d3:1319:8a2e:370:7348", "1319", "2001:db8:85a3::"),
    ],
)
def test_personal_data_is_masked(text: str, hidden: str, shown: str) -> None:
    masked = redact(text)
    assert hidden not in masked
    assert shown in masked


@pytest.mark.parametrize(
    "text",
    [
        "document 3f2b8c1e-9a4d-4c55-8e21-0b7f6a1d2c3e parse failed: ValueError",
        "2026-11-13 10:00:00,123 market refresh: 4212 postings",
        "OpenRouter failed (HTTP 429), using qwen3.5:4b",
        "analysis 42 failed after 300 s",
    ],
)
def test_ordinary_log_lines_are_left_alone(text: str) -> None:
    assert redact(text) == text


def _log_through_filter(emit: Any) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    handler.addFilter(RedactingFilter())
    logger = logging.getLogger(f"test.privacy.{id(stream)}")
    logger.propagate = False
    logger.addHandler(handler)
    emit(logger)
    return stream.getvalue()


def test_log_arguments_are_masked_and_formatting_still_works() -> None:
    output = _log_through_filter(
        lambda log: log.info(
            '%s - "%s %s" %d', "198.51.100.23:4444", "GET", "/me?email=a@b.com", 200
        )
    )
    assert output == 'INFO 198.51.100.0:4444 - "GET /me?email=[email]" 200\n'


PERSONAL = "Resume of Jane Doe: 10 years at Northwind"


def test_tracebacks_keep_frames_and_types_but_not_messages() -> None:
    # The personal text arrives as data, as it would in the app, so it isn't in any source line.
    def fail(text: str) -> None:
        try:
            raise KeyError(text)
        except KeyError as exc:
            raise ValueError(text) from exc

    def emit(log: logging.Logger) -> None:
        try:
            fail(PERSONAL)
        except ValueError:
            log.exception("analysis failed")

    output = _log_through_filter(emit)
    assert "Jane Doe" not in output
    assert "Northwind" not in output
    assert f"ValueError: {REMOVED}" in output
    assert f"KeyError: {REMOVED}" in output
    assert "in fail" in output


def test_installed_on_the_root_handlers() -> None:
    root = logging.getLogger()
    handler = logging.StreamHandler(io.StringIO())
    root.addHandler(handler)
    try:
        privacy_logging.install()
        assert any(isinstance(f, RedactingFilter) for f in handler.filters)
        privacy_logging.install()
        assert sum(isinstance(f, RedactingFilter) for f in handler.filters) == 1
    finally:
        root.removeHandler(handler)


def test_error_events_lose_request_user_and_message_details() -> None:
    event = {
        "request": {
            "method": "POST",
            "url": "https://api.example/documents?email=jane@example.com",
            "data": "resume text",
            "cookies": {"session": "x"},
            "headers": {"Authorization": "Bearer abc"},
            "query_string": "email=jane@example.com",
        },
        "user": {"id": "user-1", "email": "jane@example.com", "ip_address": "203.0.113.7"},
        "exception": {
            "values": [
                {
                    "type": "ValidationError",
                    "value": "input_value='Jane Doe, nurse at Mercy'",
                    "stacktrace": {"frames": [{"function": "analyze", "vars": {"text": "resume"}}]},
                }
            ]
        },
        "contexts": {
            "celery-job": {"task_name": "run_analysis", "args": ["a"], "kwargs": {"b": 1}}
        },
        "extra": {"resume": "text"},
        "message": "failed for jane@example.com",
    }
    scrubbed = scrub_event(event)
    serialized = json.dumps(scrubbed)
    for secret in (
        "resume text",
        "Bearer abc",
        "jane@example.com",
        "203.0.113.7",
        "Jane Doe",
        '"vars"',
        '"args"',
    ):
        assert secret not in serialized
    assert scrubbed["request"] == {"method": "POST", "url": "https://api.example/documents"}
    assert scrubbed["user"] == {"id": "user-1"}
    assert scrubbed["exception"]["values"][0]["type"] == "ValidationError"
    assert scrubbed["contexts"]["celery-job"]["task_name"] == "run_analysis"


def test_breadcrumbs_lose_query_strings() -> None:
    crumb = {
        "category": "httplib",
        "data": {
            "url": "https://x.supabase.co/rest/v1/documents?user_id=eq.1",
            "http.query": "user_id=eq.1",
        },
        "message": "jane@example.com",
    }
    scrubbed = scrub_breadcrumb(crumb)
    assert scrubbed["data"] == {"url": "https://x.supabase.co/rest/v1/documents"}
    assert scrubbed["message"] == "[email]"


def test_error_reports_are_off_without_a_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privacy_logging.settings, "sentry_dsn", "")
    assert privacy_logging.init_error_reports() is False


SENTRY_CHECK = textwrap.dedent(
    """
    import json, os
    os.environ["SENTRY_DSN"] = "https://public@sentry.invalid/1"
    import sentry_sdk
    from sentry_sdk.transport import Transport
    sent = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                if item.payload.json:
                    sent.append(item.payload.json)

    from app import privacy_logging
    from app.config import settings
    settings.sentry_dsn = os.environ["SENTRY_DSN"]
    real_init = sentry_sdk.init
    sentry_sdk.init = lambda **options: real_init(transport=Capture, **options)
    privacy_logging.init_error_reports()

    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    app = FastAPI()

    @app.post("/boom")
    async def boom(request: Request):
        resume = (await request.body()).decode()
        raise ValueError("could not read " + resume)

    TestClient(app, raise_server_exceptions=False).post(
        "/boom?email=jane@example.com",
        content="Jane Doe, nurse at Mercy, jane@example.com",
        headers={"Authorization": "Bearer abc.def", "Cookie": "session=xyz"},
    )
    sentry_sdk.flush()
    print(json.dumps(sent))
    """
)


def test_a_real_sentry_event_carries_no_personal_data() -> None:
    result = subprocess.run(
        [sys.executable, "-c", SENTRY_CHECK],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "PYTHONPATH": str(API_DIR)},
    )
    assert result.returncode == 0, result.stderr[-2000:]
    events = json.loads(result.stdout.strip().splitlines()[-1])
    errors = [event for event in events if event.get("exception")]
    assert errors, "the error reached the fake Sentry"
    serialized = json.dumps(events)
    for secret in ("Jane Doe", "Mercy", "jane@example.com", "abc.def", "xyz"):
        assert secret not in serialized
    assert errors[0]["exception"]["values"][-1]["type"] == "ValueError"


def test_http_clients_dont_log_request_urls() -> None:
    privacy_logging.install()
    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
