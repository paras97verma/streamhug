"""FFprobe runner service.

Executes ``ffprobe`` as an async subprocess, parses its JSON output,
and returns a strongly-typed :class:`MediaTechnicalInfo` object.
Results are cached per media-ID so repeated lookups are instant.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import orjson

from app.cache.manager import CacheManager
from app.core.config import Settings
from app.core.logging_config import get_logger
from app.models.media import AudioTrack, MediaTechnicalInfo, SubtitleTrack
from app.utils.paths import ffprobe_cache_path

logger = get_logger("ffprobe")
_ffmpeg_logger = get_logger("ffmpeg")


class FFprobeService:
    """Async wrapper around the ``ffprobe`` command-line tool."""

    def __init__(self, settings: Settings, cache_manager: CacheManager) -> None:
        self._settings = settings
        self._cache = cache_manager

    async def analyse(
        self, file_path: Path, media_id: str
    ) -> MediaTechnicalInfo | None:
        """Analyse a media file and return its technical metadata.

        Checks the on-disk cache first.  If the cache is stale or missing,
        runs ``ffprobe`` and persists the result.

        Args:
            file_path: Absolute path to the media file.
            media_id: Deterministic media identifier.

        Returns:
            A :class:`MediaTechnicalInfo` instance, or ``None`` on failure.
        """
        cache_file = ffprobe_cache_path(self._settings, media_id)

        # ── Cache hit check ──────────────────────────────────────────────
        if not await self._cache.is_stale(cache_file, file_path):
            cached = await self._cache.read_json(cache_file)
            if cached is not None:
                logger.debug("FFprobe cache hit: %s", media_id)
                return self._parse_cached(cached)

        # ── Run ffprobe ──────────────────────────────────────────────────
        raw = await self._run(file_path)
        if raw is None:
            return None

        info = self._parse_ffprobe_output(raw, file_path.name)
        if info is None:
            return None

        # ── Persist to cache ─────────────────────────────────────────────
        await self._cache.write_json(
            cache_file,
            info.model_dump(),
            source_path=file_path,
        )
        logger.debug("FFprobe result cached: %s", media_id)
        return info

    # ── Private helpers ──────────────────────────────────────────────────

    async def _run(self, file_path: Path) -> dict[str, Any] | None:
        """Execute ffprobe and return parsed JSON output."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path),
        ]
        _ffmpeg_logger.debug("Running: %s", " ".join(cmd))

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except FileNotFoundError:
            logger.error("ffprobe binary not found on PATH")
            return None
        except OSError as exc:
            logger.error("Failed to launch ffprobe: %s", exc)
            return None

        if process.returncode != 0:
            _ffmpeg_logger.warning(
                "ffprobe returned %d for %s: %s",
                process.returncode,
                file_path.name,
                stderr.decode(errors="replace").strip(),
            )
            return None

        try:
            return orjson.loads(stdout)
        except orjson.JSONDecodeError as exc:
            logger.error("Failed to parse ffprobe output for %s: %s", file_path.name, exc)
            return None

    @staticmethod
    def _parse_ffprobe_output(data: dict[str, Any], filename: str = "") -> MediaTechnicalInfo | None:
        """Extract a :class:`MediaTechnicalInfo` from raw ffprobe JSON.

        Collects ALL audio and subtitle streams, not just the first one.
        """
        streams: list[dict[str, Any]] = data.get("streams", [])
        fmt: dict[str, Any] = data.get("format", {})

        video_stream: dict[str, Any] | None = None
        audio_tracks: list[AudioTrack] = []
        subtitle_tracks: list[SubtitleTrack] = []

        for stream in streams:
            codec_type = stream.get("codec_type", "")
            tags: dict[str, str] = stream.get("tags", {})

            if codec_type == "video" and video_stream is None:
                video_stream = stream

            elif codec_type == "audio":
                audio_tracks.append(AudioTrack(
                    index=stream.get("index", len(audio_tracks)),
                    language=tags.get("language", tags.get("LANGUAGE", "")),
                    title=tags.get("title", tags.get("TITLE", "")),
                    codec=stream.get("codec_name", ""),
                    channels=stream.get("channels", 2),
                ))

            elif codec_type == "subtitle":
                codec = stream.get("codec_name", "")
                # Only expose text-based subtitle formats that can be converted to WebVTT
                if codec in ("subrip", "ass", "ssa", "mov_text", "webvtt", "dvd_subtitle"):
                    subtitle_tracks.append(SubtitleTrack(
                        index=stream.get("index", len(subtitle_tracks)),
                        language=tags.get("language", tags.get("LANGUAGE", "")),
                        title=tags.get("title", tags.get("TITLE", "")),
                        codec=codec,
                    ))

        if video_stream is None:
            return None

        # ── Apply Filename Heuristic for Dual Audio ──
        filename_lower = filename.lower()
        if len(audio_tracks) >= 2:
            if "[hindi.english]" in filename_lower or "hindi.english" in filename_lower or "hin.eng" in filename_lower:
                audio_tracks[0].language = "hin"
                audio_tracks[1].language = "eng"
            elif "[english.hindi]" in filename_lower or "english.hindi" in filename_lower or "eng.hin" in filename_lower:
                audio_tracks[0].language = "eng"
                audio_tracks[1].language = "hin"

        # Parse frame rate from "30/1" or "24000/1001" fraction format
        frame_rate = 0.0
        r_frame_rate = video_stream.get("r_frame_rate", "0/1")
        if "/" in r_frame_rate:
            parts = r_frame_rate.split("/")
            numerator = float(parts[0])
            denominator = float(parts[1]) if float(parts[1]) != 0 else 1.0
            frame_rate = round(numerator / denominator, 3)

        duration_seconds = float(fmt.get("duration", video_stream.get("duration", 0)))
        bitrate_kbps = int(fmt.get("bit_rate", 0)) // 1000
        file_size_bytes = int(fmt.get("size", 0))

        primary_audio_codec = audio_tracks[0].codec if audio_tracks else ""

        return MediaTechnicalInfo(
            duration_seconds=duration_seconds,
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            video_codec=video_stream.get("codec_name", "unknown"),
            audio_codec=primary_audio_codec,
            bitrate_kbps=bitrate_kbps,
            frame_rate=frame_rate,
            file_size_bytes=file_size_bytes,
            audio_tracks=audio_tracks,
            subtitle_tracks=subtitle_tracks,
        )

    @staticmethod
    def _parse_cached(data: dict[str, Any]) -> MediaTechnicalInfo | None:
        """Re-hydrate a :class:`MediaTechnicalInfo` from cached JSON."""
        try:
            # Remove the cache-internal key before parsing
            clean = {k: v for k, v in data.items() if not k.startswith("_")}
            return MediaTechnicalInfo.model_validate(clean)
        except Exception:
            return None

