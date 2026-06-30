"""Centralised path management.

All cache and media paths are resolved through this module to keep path
construction logic in a single location.  Every function ensures the
target directory exists before returning.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


# ── Video file extensions ────────────────────────────────────────────────

VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mkv", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".ts",
})


def is_video_file(path: Path) -> bool:
    """Return ``True`` if the path has a recognised video extension."""
    return path.suffix.lower() in VIDEO_EXTENSIONS


# ── Cache path helpers ───────────────────────────────────────────────────

def poster_path(settings: Settings, media_id: str) -> Path:
    """Return the absolute poster cache path for a given media ID."""
    directory = settings.poster_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{media_id}.jpg"


def banner_path(settings: Settings, media_id: str) -> Path:
    """Return the absolute banner cache path for a given media ID."""
    directory = settings.banner_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{media_id}.jpg"


def thumbnail_path(settings: Settings, media_id: str) -> Path:
    """Return the absolute thumbnail cache path for a given media ID."""
    directory = settings.thumbnail_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{media_id}.jpg"


def metadata_cache_path(settings: Settings, media_id: str) -> Path:
    """Return the JSON metadata cache path for a given media ID."""
    directory = settings.metadata_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{media_id}.json"


def ffprobe_cache_path(settings: Settings, media_id: str) -> Path:
    """Return the FFprobe result cache path for a given media ID."""
    directory = settings.metadata_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{media_id}.ffprobe.json"


# ── HLS path helpers ────────────────────────────────────────────────────

def hls_media_dir(settings: Settings, media_id: str) -> Path:
    """Return the HLS output directory for a specific media file."""
    directory = settings.hls_cache_dir / media_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def hls_quality_dir(settings: Settings, media_id: str, quality: str) -> Path:
    """Return the HLS quality-specific directory."""
    directory = settings.hls_cache_dir / media_id / quality
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def hls_master_playlist_path(settings: Settings, media_id: str) -> Path:
    """Return the path to the HLS master playlist."""
    return hls_media_dir(settings, media_id) / "master.m3u8"


def hls_variant_playlist_path(
    settings: Settings, media_id: str, quality: str
) -> Path:
    """Return the path to a quality-specific HLS variant playlist."""
    return hls_quality_dir(settings, media_id, quality) / "playlist.m3u8"
