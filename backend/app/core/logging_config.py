"""Structured logging configuration.

Sets up three log destinations:
  1. Console (stderr) — human-readable, coloured output
  2. App log file — rotating file handler for application events
  3. FFmpeg log file — separate rotating file for FFmpeg/FFprobe output
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

# 10 MB per file, keep 5 backups
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, *, debug: bool = False) -> None:
    """Initialise the global logging configuration.

    This function is idempotent — calling it more than once is a no-op.

    Args:
        log_dir: Directory where log files are written.
        debug: When ``True``, the root logger level is set to ``DEBUG``.
    """
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return
    _CONFIGURED = True

    log_dir.mkdir(parents=True, exist_ok=True)
    root_level = logging.DEBUG if debug else logging.INFO

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # ── Console handler ──────────────────────────────────────────────────
    console_handler = logging.StreamHandler(stream=sys.stderr)
    console_handler.setLevel(root_level)
    console_handler.setFormatter(formatter)

    # ── App file handler ─────────────────────────────────────────────────
    app_handler = RotatingFileHandler(
        filename=log_dir / "streamhug.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(root_level)
    app_handler.setFormatter(formatter)

    # ── FFmpeg file handler ──────────────────────────────────────────────
    ffmpeg_handler = RotatingFileHandler(
        filename=log_dir / "ffmpeg.log",
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    ffmpeg_handler.setLevel(logging.DEBUG)
    ffmpeg_handler.setFormatter(formatter)

    # ── Root logger ──────────────────────────────────────────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(root_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)

    # ── FFmpeg-specific logger ───────────────────────────────────────────
    ffmpeg_logger = logging.getLogger("streamhug.ffmpeg")
    ffmpeg_logger.propagate = False
    ffmpeg_logger.setLevel(logging.DEBUG)
    ffmpeg_logger.addHandler(ffmpeg_handler)
    ffmpeg_logger.addHandler(console_handler)

    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger under the ``streamhug`` hierarchy.

    Args:
        name: Dot-separated logger name, e.g. ``"services.hls"``.

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(f"streamhug.{name}")
