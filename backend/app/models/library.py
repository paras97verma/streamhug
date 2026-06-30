"""Library aggregation models.

A ``Library`` groups all discovered media into categorised collections.
``LibrarySummary`` provides lightweight counts for UI dashboards.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.media import Media


class Library(BaseModel):
    """The complete in-memory media library, organised by category."""

    movies: list[Media] = Field(default_factory=list)
    tv_shows: list[Media] = Field(default_factory=list)
    anime: list[Media] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.movies) + len(self.tv_shows) + len(self.anime)


class LibrarySummary(BaseModel):
    """Lightweight counts for each media category."""

    movies: int = 0
    tv_shows: int = 0
    anime: int = 0
    total: int = 0
