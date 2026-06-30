"""API response wrappers.

Every endpoint returns a standardised envelope wrapping the actual payload.
This ensures consistency for the frontend consumer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.library import Library, LibrarySummary
from app.models.media import Media, MediaTechnicalInfo


class HealthResponse(BaseModel):
    """Response for ``GET /api/v1/health``."""

    status: str = "ok"
    version: str = "1.0.0"
    media_count: int = 0
    tunnel_public_url: str = ""
    websocket_enabled: bool = True
    redis_enabled: bool = False


class LibraryResponse(BaseModel):
    """Response for ``GET /api/v1/library``."""

    library: Library
    summary: LibrarySummary


class MediaDetailResponse(BaseModel):
    """Response for ``GET /api/v1/movie/{id}``."""

    media: Media | None = None
    technical_info: MediaTechnicalInfo | None = None


class SearchResponse(BaseModel):
    """Response for ``GET /api/v1/search``."""

    query: str
    results: list[Media] = Field(default_factory=list)
    total: int = 0
