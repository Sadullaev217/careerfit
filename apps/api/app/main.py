import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.file_validation import MAX_FILE_BYTES
from app.routers import account, documents, health, market

logger = logging.getLogger(__name__)

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


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

app.add_middleware(MaxBodySizeMiddleware, max_bytes=MAX_REQUEST_BYTES)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
