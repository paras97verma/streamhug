"""File-based JSON cache manager.

Provides async read / write / invalidation for JSON-serialisable data.
Staleness is detected by comparing the cached ``source_mtime_ns`` against
the current source file mtime.

All disk I/O goes through :mod:`aiofiles` to avoid blocking the event loop.
Serialisation uses :mod:`orjson` for speed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiofiles
import orjson

from app.core.config import Settings
from app.core.logging_config import get_logger

logger = get_logger("cache")

try:
    from redis.asyncio import Redis
except Exception:  # pragma: no cover - optional dependency
    Redis = None  # type: ignore[assignment]


class CacheManager:
    """Async file-based JSON cache with staleness detection."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._redis: Redis | None = None  # type: ignore[valid-type]

    async def connect(self) -> None:
        if not self._settings.redis_url or Redis is None:
            if self._settings.redis_url and Redis is None:
                logger.warning("REDIS_URL configured but redis package is not installed")
            return
        try:
            self._redis = Redis.from_url(
                self._settings.redis_url,
                decode_responses=False,
            )
            await self._redis.ping()
            logger.info("Connected to Redis metadata cache")
        except Exception as exc:
            logger.warning("Redis unavailable, continuing with file cache only: %s", exc)
            self._redis = None

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    # ── Public API ───────────────────────────────────────────────────────

    async def read_json(self, cache_path: Path) -> dict[str, Any] | None:
        """Read and deserialise a JSON cache file.

        Returns ``None`` if the file does not exist or is malformed.
        """
        cache_key = self._redis_key(cache_path)
        if self._redis is not None:
            try:
                cached = await self._redis.get(cache_key)
                if cached is not None:
                    return orjson.loads(cached)
            except Exception as exc:
                logger.debug("Redis read failed for %s: %s", cache_key, exc)
        if not cache_path.is_file():
            return None
        try:
            async with aiofiles.open(cache_path, "rb") as fh:
                raw = await fh.read()
            return orjson.loads(raw)
        except (orjson.JSONDecodeError, OSError) as exc:
            logger.warning("Cache read failed for %s: %s", cache_path.name, exc)
            return None

    async def write_json(
        self,
        cache_path: Path,
        data: dict[str, Any],
        *,
        source_path: Path | None = None,
    ) -> None:
        """Serialise *data* to a JSON cache file.

        If *source_path* is provided, the source file's mtime is embedded
        in the cached payload under the ``_source_mtime_ns`` key so that
        :meth:`is_stale` can detect changes.
        """
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(data)
        if source_path is not None and source_path.is_file():
            payload["_source_mtime_ns"] = source_path.stat().st_mtime_ns
        raw = orjson.dumps(payload, option=orjson.OPT_INDENT_2)
        if self._redis is not None:
            try:
                await self._redis.set(
                    self._redis_key(cache_path),
                    raw,
                    ex=self._settings.redis_metadata_ttl_seconds,
                )
            except Exception as exc:
                logger.debug("Redis write failed for %s: %s", cache_path.name, exc)
        async with aiofiles.open(cache_path, "wb") as fh:
            await fh.write(raw)
        logger.debug("Cache written: %s", cache_path.name)

    async def is_stale(
        self, cache_path: Path, source_path: Path
    ) -> bool:
        """Return ``True`` when the cache is missing or outdated.

        The cache is considered stale when:
          - The cache file does not exist.
          - The source file does not exist.
          - The cached ``_source_mtime_ns`` differs from the current mtime.
        """
        if not cache_path.is_file():
            return True
        if not source_path.is_file():
            return True
        cached = await self.read_json(cache_path)
        if cached is None:
            return True
        cached_mtime = cached.get("_source_mtime_ns")
        if cached_mtime is None:
            return True
        return int(cached_mtime) != source_path.stat().st_mtime_ns

    async def invalidate(self, cache_path: Path) -> None:
        """Delete a cache file if it exists."""
        if cache_path.is_file():
            cache_path.unlink(missing_ok=True)
            logger.debug("Cache invalidated: %s", cache_path.name)
        if self._redis is not None:
            try:
                await self._redis.delete(self._redis_key(cache_path))
            except Exception as exc:
                logger.debug("Redis invalidate failed for %s: %s", cache_path.name, exc)

    async def has_file(self, path: Path) -> bool:
        """Return ``True`` if a file exists at the given path."""
        return path.is_file()

    def _redis_key(self, cache_path: Path) -> str:
        return f"streamhug:cache:{cache_path.as_posix()}"
