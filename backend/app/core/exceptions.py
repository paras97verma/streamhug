"""Structured exception handlers.

Provides a consistent JSON error envelope for all unhandled exceptions
and HTTP errors so the frontend always receives a predictable shape.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging_config import get_logger

logger = get_logger("exceptions")


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI application."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> ORJSONResponse:
        """Return a consistent JSON envelope for HTTP exceptions."""
        request_id = getattr(request.state, "request_id", None)
        return ORJSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "detail": exc.detail,
                "request_id": request_id,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> ORJSONResponse:
        """Return a structured 422 response for validation failures."""
        request_id = getattr(request.state, "request_id", None)
        errors = []
        for err in exc.errors():
            errors.append({
                "field": " → ".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            })
        return ORJSONResponse(
            status_code=422,
            content={
                "error": True,
                "status_code": 422,
                "detail": "Validation error",
                "errors": errors,
                "request_id": request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> ORJSONResponse:
        """Catch-all for unhandled exceptions — logs the traceback and
        returns a generic 500 response without leaking internals."""
        request_id = getattr(request.state, "request_id", None)
        logger.exception(
            "Unhandled exception on %s %s [%s]: %s",
            request.method,
            request.url.path,
            request_id,
            exc,
        )
        return ORJSONResponse(
            status_code=500,
            content={
                "error": True,
                "status_code": 500,
                "detail": "Internal server error",
                "request_id": request_id,
            },
        )
