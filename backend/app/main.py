"""StreamHug — Application entry point.

Creates the FastAPI application with:
  - Configurable API version prefix (``/api/{version}``)
  - CORS middleware (permissive for ngrok)
  - Request ID, logging, and security headers middleware
  - Global exception handlers with consistent JSON envelopes
  - Proper FastAPI ``Depends()`` injection
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.lifespan import lifespan
from app.core.middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)


def create_app() -> FastAPI:
    """Application factory — builds and configures the FastAPI instance."""
    settings = get_settings()
    api_prefix = settings.api_prefix  # e.g. "/api/v1"

    application = FastAPI(
        title="StreamHug",
        description="Personal media streaming server",
        version="1.0.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url=f"{api_prefix}/docs",
        redoc_url=f"{api_prefix}/redoc",
        openapi_url=f"{api_prefix}/openapi.json",
    )

    # ── Middleware (applied in reverse order — last added runs first) ─────

    # 1. CORS — outermost so preflight requests are handled immediately
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
    )

    # 2. Security headers
    application.add_middleware(SecurityHeadersMiddleware)

    # 3. Request logging with timing
    application.add_middleware(RequestLoggingMiddleware)

    if settings.rate_limit_enabled:
        application.add_middleware(
            RateLimitMiddleware,
            requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window_seconds,
        )

    # 4. Request ID — innermost so it runs first and is available to all others
    application.add_middleware(RequestIDMiddleware)

    # ── Exception handlers ───────────────────────────────────────────────
    register_exception_handlers(application)

    # ── Routes — prefix comes from settings, never hardcoded ─────────────
    application.include_router(api_router, prefix=api_prefix)

    return application


app = create_app()
