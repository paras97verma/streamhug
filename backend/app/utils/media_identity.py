"""Deterministic media identity generation.

Each media file is assigned a stable, URL-safe identifier derived from its
absolute path and last-modified timestamp.  When the source file changes
(different mtime), the ID changes automatically, which invalidates all
cached artefacts for that file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def generate_media_id(file_path: Path) -> str:
    """Create a deterministic, URL-safe identifier for a media file.

    The ID is a truncated SHA-256 hex digest of the file's absolute path
    concatenated with its ``st_mtime_ns`` (nanosecond-precision mtime).
    This ensures:
      - Same file → same ID (deterministic)
      - Modified file → different ID (cache invalidation)
      - URL-safe output (hex characters only)

    Args:
        file_path: Absolute path to the media file.  Must exist on disk.

    Returns:
        A 16-character lowercase hex string.
    """
    stat = file_path.stat()
    identity_string = f"{file_path.resolve()}:{stat.st_mtime_ns}"
    digest = hashlib.sha256(identity_string.encode("utf-8")).hexdigest()
    return digest[:16]


def generate_series_id(series_dir: Path) -> str:
    """Create a deterministic ID for a series directory.

    Unlike individual file IDs, a series ID is based solely on the
    directory path (not mtime) so it remains stable across episode
    additions and re-scans.

    Args:
        series_dir: Absolute path to the series root directory.

    Returns:
        A 16-character lowercase hex string.
    """
    identity_string = str(series_dir.resolve())
    digest = hashlib.sha256(identity_string.encode("utf-8")).hexdigest()
    return digest[:16]
