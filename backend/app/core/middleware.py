"""Production middleware stack.

Provides:
  - **RequestIDMiddleware** — attaches a unique ``X-Request-ID`` header to
    every request and response for log correlation.
  - **RequestLoggingMiddleware** — logs method, path, status, and duration
    for every request.
  - **SecurityHeadersMiddleware** — adds standard security headers to all
    responses.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.logging_config import get_logger

logger = get_logger("middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request / response cycle.

    If the client sends an ``X-Request-ID`` header it is reused; otherwise
    a new UUID4 is generated.  The ID is added to the response headers and
    stored on ``request.state.request_id`` for downstream logging.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"

        # Skip noisy health-check logging in production
        path = request.url.path
        if not path.endswith("/health"):
            request_id = getattr(request.state, "request_id", "???")
            logger.info(
                "%s %s → %d (%.1fms) [%s]",
                request.method,
                path,
                response.status_code,
                duration_ms,
                request_id,
            )

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers to every response.

    These headers provide defence-in-depth against common web attacks
    without interfering with the HLS streaming or ngrok tunnelling.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small in-process IP rate limiter for control-plane endpoints."""

    def __init__(self, app, *, requests: int, window_seconds: int) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._requests = requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path.endswith((".m3u8", ".m4s", ".mp4", ".ts", ".vtt")):
            return await call_next(request)

        now = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"
        bucket = self._buckets[client_ip]
        cutoff = now - self._window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= self._requests:
            response = Response(
                content='{"error":true,"detail":"Rate limit exceeded"}',
                media_type="application/json",
                status_code=HTTP_429_TOO_MANY_REQUESTS,
            )
            headers = MutableHeaders(response.headers)
            headers["Retry-After"] = str(self._window_seconds)
            return response

        bucket.append(now)
        return await call_next(request)
