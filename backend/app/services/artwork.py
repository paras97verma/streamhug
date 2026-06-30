"""Artwork service — poster and banner generation.

Handles two strategies:

1. **TMDB mode** — downloads poster and banner images from TMDB CDN.
2. **Fallback mode** — extracts a single frame at the 15-second mark via
   FFmpeg and uses it as both poster and banner.

All generated artwork is cached on disk.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.metadata import MetadataService
from app.utils import paths as path_utils

logger = get_logger("artwork")
_ffmpeg_logger = get_logger("ffmpeg")


class ArtworkService:
    """Generates and caches poster and banner images for media items."""

    def __init__(self, settings: Settings, metadata_service: MetadataService) -> None:
        self._settings = settings
        self._metadata = metadata_service

    async def ensure_artwork(
        self,
        media_id: str,
        file_path: Path,
        metadata: dict[str, Any],
    ) -> tuple[str, str]:
        """Ensure poster and banner images exist for a media item.

        Returns:
            A tuple of ``(poster_relative_path, banner_relative_path)``
            relative to the cache root.
        """
        poster_file = path_utils.poster_path(self._settings, media_id)
        banner_file = path_utils.banner_path(self._settings, media_id)

        poster_exists = poster_file.is_file()
        banner_exists = banner_file.is_file()

        if poster_exists and banner_exists:
            return self._relative_paths(poster_file, banner_file)

        poster_url = metadata.get("poster_url", "")
        banner_url = metadata.get("banner_url", "")

        # ── Download from TMDB if URLs available ─────────────────────────
        if poster_url and not poster_exists:
            await self._download_image(poster_url, poster_file)
            poster_exists = poster_file.is_file()

        if banner_url and not banner_exists:
            await self._download_image(banner_url, banner_file)
            banner_exists = banner_file.is_file()

        # ── FFmpeg fallback: extract frame at 15s ────────────────────────
        if not poster_exists:
            await self._extract_frame(file_path, poster_file)
            poster_exists = poster_file.is_file()

        if not banner_exists:
            # Re-use the poster as the banner
            if poster_exists:
                await self._copy_as_banner(poster_file, banner_file)
            else:
                await self._extract_frame(file_path, banner_file)

        return self._relative_paths(poster_file, banner_file)

    # ── Private helpers ──────────────────────────────────────────────────

    def _relative_paths(self, poster: Path, banner: Path) -> tuple[str, str]:
        """Return cache-relative string paths."""
        cache_root = self._settings.cache_root
        poster_rel = str(poster.relative_to(cache_root)) if poster.is_file() else ""
        banner_rel = str(banner.relative_to(cache_root)) if banner.is_file() else ""
        return poster_rel, banner_rel

    @staticmethod
    async def _download_image(url: str, dest: Path) -> None:
        """Download an image from a URL and save to disk."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                response = await client.get(url)
                response.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(response.content)
                logger.debug("Downloaded artwork: %s", dest.name)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Failed to download %s: %s", url, exc)

    @staticmethod
    async def _extract_frame(source: Path, dest: Path) -> None:
        """Extract a single frame at the 15-second mark using FFmpeg."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", "15",
            "-i", str(source),
            "-frames:v", "1",
            "-q:v", "2",
            "-vf", "scale=640:-2",
            str(dest),
        ]
        _ffmpeg_logger.debug("Extracting frame: %s", " ".join(cmd))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                _ffmpeg_logger.warning(
                    "Frame extraction failed for %s: %s",
                    source.name,
                    stderr.decode(errors="replace").strip(),
                )
            else:
                logger.debug("Frame extracted: %s", dest.name)
        except FileNotFoundError:
            logger.error("ffmpeg binary not found on PATH")
        except OSError as exc:
            logger.error("Failed to run ffmpeg: %s", exc)

    @staticmethod
    async def _copy_as_banner(poster: Path, banner: Path) -> None:
        """Copy the poster file to serve as the banner."""
        import shutil

        banner.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(poster, banner)
            logger.debug("Poster copied as banner: %s", banner.name)
        except OSError as exc:
            logger.warning("Failed to copy poster to banner: %s", exc)
