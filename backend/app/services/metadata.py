"""Metadata service — TMDB lookups with filename-parsed fallback.

When a TMDB API key is configured, searches for movie / TV show metadata
including title, year, overview, and image URLs.  Otherwise, metadata is
derived entirely from the on-disk filename and directory structure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from app.cache.manager import CacheManager
from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.media import MediaType
from app.utils.paths import metadata_cache_path

logger = get_logger("metadata")


class _TMDBResult:
    """Internal container for a TMDB API result."""

    __slots__ = ("title", "year", "overview", "poster_url", "banner_url")

    def __init__(
        self,
        title: str = "",
        year: int | None = None,
        overview: str = "",
        poster_url: str = "",
        banner_url: str = "",
    ) -> None:
        self.title = title
        self.year = year
        self.overview = overview
        self.poster_url = poster_url
        self.banner_url = banner_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "year": self.year,
            "overview": self.overview,
            "poster_url": self.poster_url,
            "banner_url": self.banner_url,
        }


class MetadataService:
    """Fetches and caches media metadata from TMDB or filename parsing."""

    def __init__(self, settings: Settings, cache_manager: CacheManager) -> None:
        self._settings = settings
        self._cache = cache_manager
        self._client: httpx.AsyncClient | None = None
        if settings.has_tmdb:
            self._client = httpx.AsyncClient(
                base_url=settings.tmdb_base_url,
                params={"api_key": settings.tmdb_api_key},
                timeout=httpx.Timeout(10.0),
            )

    async def close(self) -> None:
        """Gracefully close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_metadata(
        self,
        media_id: str,
        title: str,
        year: int | None,
        media_type: MediaType,
        source_path: Path,
    ) -> dict[str, Any]:
        """Return metadata for a media item.

        Checks the on-disk cache first.  If stale or missing, fetches
        fresh data from TMDB (if available) and caches the result.

        Args:
            media_id: Deterministic identifier.
            title: Parsed or known title.
            year: Release year (may be ``None``).
            media_type: The category of media.
            source_path: Path to the source file (for staleness checks).

        Returns:
            A dictionary with ``title``, ``year``, ``overview``,
            ``poster_url``, ``banner_url``.
        """
        cache_file = metadata_cache_path(self._settings, media_id)

        if not await self._cache.is_stale(cache_file, source_path):
            cached = await self._cache.read_json(cache_file)
            if cached is not None:
                logger.debug("Metadata cache hit: %s", media_id)
                clean = {k: v for k, v in cached.items() if not k.startswith("_")}
                return clean

        result: _TMDBResult
        if self._client is not None:
            result = await self._search_tmdb(title, year, media_type)
        else:
            result = _TMDBResult(title=title, year=year)

        await self._cache.write_json(
            cache_file, result.to_dict(), source_path=source_path
        )
        logger.debug("Metadata cached: %s (%s)", title, media_id)
        return result.to_dict()

    # ── TMDB search ──────────────────────────────────────────────────────

    async def _search_tmdb(
        self, title: str, year: int | None, media_type: MediaType
    ) -> _TMDBResult:
        """Query the TMDB search endpoint and return the best match."""
        if self._client is None:
            return _TMDBResult(title=title, year=year)

        search_type = "movie" if media_type == MediaType.MOVIE else "tv"
        params: dict[str, str | int] = {"query": title}
        if year is not None and year > 0:
            if search_type == "movie":
                params["year"] = year
            else:
                params["first_air_date_year"] = year

        try:
            response = await self._client.get(f"/search/{search_type}", params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, Exception) as exc:
            logger.warning("TMDB search failed for '%s': %s", title, exc)
            return _TMDBResult(title=title, year=year)

        results = data.get("results", [])
        if not results:
            logger.debug("TMDB: no results for '%s'", title)
            return _TMDBResult(title=title, year=year)

        hit = results[0]
        image_base = self._settings.tmdb_image_base_url

        tmdb_title = hit.get("title") or hit.get("name") or title
        release = hit.get("release_date") or hit.get("first_air_date") or ""
        tmdb_year = int(release[:4]) if len(release) >= 4 else year

        poster_path = hit.get("poster_path", "")
        banner_path = hit.get("backdrop_path", "")

        return _TMDBResult(
            title=tmdb_title,
            year=tmdb_year,
            overview=hit.get("overview", ""),
            poster_url=f"{image_base}/w500{poster_path}" if poster_path else "",
            banner_url=f"{image_base}/w1280{banner_path}" if banner_path else "",
        )
