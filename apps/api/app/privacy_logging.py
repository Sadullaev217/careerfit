"""Keeps personal data out of logs and error reports.

The code never logs resume text on purpose, but an exception message can still carry it (a validation error
quotes its input, for example), and access logs carry addresses and push tokens. So:

- every log line has emails, phone numbers, tokens, keys and push tokens masked, and IP addresses shortened;
- tracebacks keep their frames and exception types but drop exception messages;
- Sentry, when SENTRY_DSN is set, gets no request bodies, cookies, headers, query strings, local variables,
  user details or exception messages, and the same masking on everything else.
"""

import logging
import re
import traceback
import types
from collections.abc import Mapping
from typing import Any

from app.config import settings

REMOVED = "[removed]"

_PATTERNS = [
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "[token]"),
    (re.compile(r"(?i)\bbearer\s+[\w.~+/=-]+"), "Bearer [token]"),
    (
        re.compile(
            r"\b(?:sk|rk|pk)_(?:test|live)_\w+|\bwhsec_\w+|\bsb_secret_\w+|\bsk-(?:or-v1|ant)-[\w-]+"
        ),
        "[secret]",
    ),
    (re.compile(r"Expo(?:nent)?PushToken\[[^\]]*\]"), "ExponentPushToken[…]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (
        re.compile(r"(?<![\w-])\+\d{1,3}[\s.-]?\(?\d{1,4}\)?(?:[\s.-]?\d{2,4}){2,3}(?![\w-])"),
        "[phone]",
    ),
    (re.compile(r"(?<![\w-])\(\d{3}\)\s?\d{3}[\s.-]\d{4}(?![\w-])"), "[phone]"),
    (re.compile(r"(?<![\w.-])\d{3}[.-]\d{3}[.-]\d{4}(?![\w.-])"), "[phone]"),
    # The last part of an IPv4 address, and everything after the third group of an IPv6 one.
    (re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}\b"), r"\1.0"),
    (re.compile(r"\b([0-9a-fA-F]{1,4}:[0-9a-fA-F]{1,4}:[0-9a-fA-F]{1,4}):[0-9a-fA-F:]+"), r"\1::"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def safe_traceback(exc_info: tuple[Any, ...]) -> str:
    """The traceback with each exception's type and frames, but not its message."""
    exc = exc_info[1]
    parts: list[str] = []
    seen: set[int] = set()
    while isinstance(exc, BaseException) and id(exc) not in seen:
        seen.add(id(exc))
        frames = "".join(_format_frames(exc.__traceback__))
        parts.append(
            f"Traceback (most recent call last):\n{frames}{type(exc).__qualname__}: {REMOVED}"
        )
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    return "\n\nWhile handling or caused by:\n".join(reversed(parts))


def _format_frames(tb: types.TracebackType | None) -> list[str]:
    return traceback.format_tb(tb)


def _redact_value(value: Any) -> Any:
    return redact(value) if isinstance(value, str) else value


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_value(arg) for arg in record.args)
        elif isinstance(record.args, Mapping):
            record.args = {key: _redact_value(arg) for key, arg in record.args.items()}
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = safe_traceback(record.exc_info)
        return True


_LOGGERS = (
    "",
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "celery",
    "celery.task",
    "celery.worker",
)


def install() -> None:
    """Adds the filter to every handler that writes logs, giving the root logger one if it has none."""
    root = logging.getLogger()
    if not root.handlers:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(stream)
        root.setLevel(logging.INFO)
    for name in _LOGGERS:
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, RedactingFilter) for f in handler.filters):
                handler.addFilter(RedactingFilter())


# --- Sentry -------------------------------------------------------------------------------------------


def _scrub_strings(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return [_scrub_strings(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_strings(item) for key, item in value.items()}
    return value


def _without_query(url: Any) -> Any:
    return url.split("?", 1)[0] if isinstance(url, str) else url


def scrub_event(event: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict):
        event["request"] = {
            "method": request.get("method"),
            "url": _without_query(request.get("url")),
        }
    user = event.get("user")
    event["user"] = {"id": user["id"]} if isinstance(user, dict) and user.get("id") else {}
    for exception in (event.get("exception") or {}).get("values") or []:
        if exception.get("value"):
            exception["value"] = REMOVED
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    job = (event.get("contexts") or {}).get("celery-job")
    if isinstance(job, dict):
        job.pop("args", None)
        job.pop("kwargs", None)
    event.pop("extra", None)
    scrubbed: dict[str, Any] = _scrub_strings(event)
    return scrubbed


def scrub_breadcrumb(crumb: dict[str, Any], _hint: dict[str, Any] | None = None) -> dict[str, Any]:
    data = crumb.get("data")
    if isinstance(data, dict) and "url" in data:
        data["url"] = _without_query(data["url"])
        data.pop("http.query", None)
    scrubbed: dict[str, Any] = _scrub_strings(crumb)
    return scrubbed


def init_error_reports() -> bool:
    """Starts Sentry when SENTRY_DSN is set. Returns whether it did."""
    if not settings.sentry_dsn:
        return False
    import sentry_sdk

    if sentry_sdk.is_initialized():
        return True
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.app_version,
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        before_send=scrub_event,  # type: ignore[arg-type]
        before_breadcrumb=scrub_breadcrumb,
        traces_sample_rate=0,
    )
    return True
