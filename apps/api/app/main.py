import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app import privacy_logging, rate_limit
from app.config import settings
from app.file_validation import MAX_FILE_BYTES
from app.routers import account, analyses, billing, documents, health, market, notifications

logger = logging.getLogger(__name__)

privacy_logging.install()
privacy_logging.init_error_reports()

# Bodies are spooled to disk before auth runs, so the limit has to apply earlier than the routes.
MAX_REQUEST_BYTES = MAX_FILE_BYTES + 1024 * 1024


class BodyTooLarge(Exception):
    pass


class MaxBodySizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            {"detail": {"code": "too_large", "message": "This file is larger than the 10 MB limit."}},
            status_code=413,
        )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length", b"0")
        if declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except BodyTooLarge:
            await self._reject(scope, receive, send)


# Paths every address may call without counting: the uptime check, and Stripe, which retries on its own.
UNLIMITED_PATHS = frozenset({"/health", "/billing/stripe-webhook"})


class AddressLimitMiddleware:
    """The general allowance per network address (see app/rate_limit.py)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] in UNLIMITED_PATHS:
            await self.app(scope, receive, send)
            return
        # Behind a proxy this is the visitor's address only when uvicorn runs with --proxy-headers.
        client = scope.get("client")
        try:
            rate_limit.check(rate_limit.PER_ADDRESS, "address", client[0] if client else "unknown")
        except rate_limit.Limited as exc:
            response = JSONResponse(
                {"detail": {"code": "rate_limited", "message": rate_limit.MESSAGE}},
                status_code=429,
                headers={"Retry-After": str(exc.retry_after)},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


# The API only returns JSON and PDFs, so nothing in a response may load scripts, be framed or be cached.
SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-opener-policy": "same-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "cache-control": "no-store",
}
# The interactive docs, served only with DEBUG on, need their own scripts.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, https_only: bool) -> None:
        self.app = app
        self.https_only = https_only

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        docs = scope["path"].startswith(DOCS_PATHS)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    if not (docs and name == "content-security-policy"):
                        headers.setdefault(name, value)
                if self.https_only:
                    # Browsers then refuse plain http to the API for two years, including links to it.
                    headers["strict-transport-security"] = "max-age=63072000; includeSubDomains"
            await send(message)

        await self.app(scope, receive, send_with_headers)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Outermost last: every response, refusals included, gets the security headers, and CORS headers so the
# web app can read a refusal.
app.add_middleware(MaxBodySizeMiddleware, max_bytes=MAX_REQUEST_BYTES)
app.add_middleware(AddressLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    # Apps send a bearer token, never cookies, so browsers are told not to send credentials.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
    max_age=600,
)
app.add_middleware(SecurityHeadersMiddleware, https_only=settings.deployed)


@app.exception_handler(httpx.HTTPError)
def storage_unavailable(_request: Request, exc: httpx.HTTPError) -> JSONResponse:
    logger.error("upstream request failed: %s", type(exc).__name__)
    return JSONResponse(
        {
            "detail": {
                "code": "storage_unavailable",
                "message": "We couldn't save your request. Please try again.",
            }
        },
        status_code=502,
    )


app.include_router(health.router)
app.include_router(account.router)
app.include_router(documents.router)
app.include_router(market.router)
app.include_router(analyses.router)
app.include_router(notifications.router)
app.include_router(billing.router)
