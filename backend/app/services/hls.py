"""HLS adaptive streaming service with on-demand CMAF generation.

Optimised for ultra-fast startup and instant seeking:
- Only the *requested* quality is transcoded, not all presets at once.
- FFmpeg uses ``-preset ultrafast -tune zerolatency`` for minimal first-segment delay.
- Seeking kills the current transcode and restarts from the seek point.
- ``init.mp4`` is served explicitly; segment polling is production-grade.
- Separate audio renditions with correct track mapping for multi-audio files.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.events import EventService
from app.services.metrics import MetricsService
from app.utils import paths as path_utils

logger = get_logger("hls")
_ffmpeg_logger = get_logger("ffmpeg")


@dataclass(frozen=True, slots=True)
class QualityPreset:
    name: str
    height: int
    video_bitrate: str
    audio_bitrate: str
    bandwidth: int


@dataclass(slots=True)
class TranscodeRequest:
    media_id: str
    source_path: Path
    preset: QualityPreset
    start_segment: int = 0
    kind: str = "video"


QUALITY_PRESETS: dict[str, QualityPreset] = {
    "1080p": QualityPreset("1080p", 1080, "3000k", "192k", 3_200_000),
    "720p": QualityPreset("720p", 720, "1500k", "128k", 1_700_000),
    "480p": QualityPreset("480p", 480, "800k", "128k", 1_000_000),
    "360p": QualityPreset("360p", 360, "400k", "96k", 500_000),
    "240p": QualityPreset("240p", 240, "250k", "64k", 350_000),
}


class HLSService:
    """Generates and serves on-demand HLS/CMAF assets with persistent cache reuse."""

    def __init__(
        self,
        settings: Settings,
        event_service: EventService | None = None,
        metrics_service: MetricsService | None = None,
    ) -> None:
        self._settings = settings
        self._events = event_service
        self._metrics = metrics_service
        self._semaphore = asyncio.Semaphore(settings.hls_max_concurrent_transcodes)
        self._job_queue: asyncio.Queue[TranscodeRequest] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._queued_keys: set[str] = set()
        self._active_tasks: dict[str, asyncio.Task[None]] = {}
        self._active_processes: dict[str, asyncio.subprocess.Process] = {}
        self._shutdown = False
        self._cleanup_stale_caches()
        self._start_workers()

    # ── Public API ──────────────────────────────────────────────────────

    async def get_master_playlist(self, media_id: str, source_path: Path) -> Path | None:
        await self.ensure_media_ready(media_id, source_path)
        master_path = path_utils.hls_master_playlist_path(self._settings, media_id)
        return master_path if master_path.is_file() else None

    async def ensure_media_ready(self, media_id: str, source_path: Path) -> None:
        """Prepare master and variant manifests early so playback can start faster."""
        if self._is_stale(media_id, source_path):
            self._cleanup_hls_cache(media_id)

        hls_dir = path_utils.hls_media_dir(self._settings, media_id)
        hls_dir.mkdir(parents=True, exist_ok=True)
        duration = await self._get_duration(source_path)
        if duration is None or duration <= 0:
            raise RuntimeError(f"Unable to determine duration for {source_path.name}")

        self._write_media_manifest(media_id, source_path, duration)

        # Get video width to avoid upscaling
        source_width = await self._get_video_width(source_path)

        # Detect audio tracks for the master playlist
        audio_tracks = await self._detect_audio_tracks(source_path)
        self._write_master_playlist(media_id, source_width, audio_tracks)

        # Write estimated variant playlists for included resolutions
        for preset in QUALITY_PRESETS.values():
            preset_width = preset.height * 16 // 9
            if source_width is not None and preset_width > source_width + 50:
                continue
            self._write_estimated_variant_playlist(media_id, duration, preset.name)

        # Write estimated audio playlists for each track
        for track in audio_tracks:
            self._write_estimated_audio_playlist(media_id, duration, track["index"])

        # DON'T enqueue all qualities. Only enqueue when actually requested.

    async def start_early_transcoding(self, media_id: str, source_path: Path) -> None:
        await self.ensure_media_ready(media_id, source_path)
        
        # Kill other media transcodes to free up system resources immediately
        default_quality = self._settings.hls_default_quality
        await self._cancel_distant_transcodes(media_id, default_quality, None)
        
        # Only enqueue the default quality for early start
        default_preset = QUALITY_PRESETS.get(default_quality, QUALITY_PRESETS["720p"])
        await self._enqueue_video_job(media_id, source_path, default_preset)

    async def get_segment_path(
        self, media_id: str, quality: str, segment: str, source_path: Path
    ) -> Path | None:
        preset = QUALITY_PRESETS.get(quality)
        if preset is None:
            return None

        await self.ensure_media_ready(media_id, source_path)
        quality_dir = path_utils.hls_quality_dir(self._settings, media_id, quality)

        # ── Handle init.mp4 explicitly ───────────────────────────────────
        if segment == "init.mp4":
            target = quality_dir / "init.mp4"
            if target.is_file():
                return target
                
            # Cancel competing transcodes for other qualities to free CPU immediately,
            # but don't kill transcodes for the SAME quality (pass target_segment=None)
            await self._cancel_distant_transcodes(media_id, quality, None)
            
            # Check if there is already an active or queued job for this quality
            has_job = False
            for key in list(self._active_tasks.keys()) + list(self._queued_keys):
                parts = key.split(":")
                if len(parts) >= 2 and parts[0] == media_id and parts[1] == quality:
                    has_job = True
                    break
            
            if not has_job:
                # init.mp4 is created by the first transcode job; enqueue it
                await self._enqueue_video_job(media_id, source_path, preset, start_segment=0)
                
            for _ in range(240):  # 60 seconds
                if target.is_file():
                    return target
                await asyncio.sleep(0.25)
            return target if target.is_file() else None

        # ── Handle regular segments ──────────────────────────────────────
        target = quality_dir / segment
        if target.is_file():
            await self._maybe_prefetch(media_id, source_path, preset, segment)
            return target

        seg_index = self._segment_index(segment)

        # Cancel far-away transcodes for this media+quality to free CPU for the
        # requested segment (critical for instant seek)
        await self._cancel_distant_transcodes(media_id, quality, seg_index)

        await self._enqueue_video_job(
            media_id, source_path, preset, start_segment=seg_index,
        )

        # Poll for the segment with production-grade timeout (60s)
        for _ in range(240):
            if target.is_file():
                await self._maybe_prefetch(media_id, source_path, preset, segment)
                return target
            await asyncio.sleep(0.25)
        return target if target.is_file() else None

    async def get_audio_track_playlist(
        self, media_id: str, source_path: Path, track_index: int
    ) -> Path | None:
        await self.ensure_media_ready(media_id, source_path)
        hls_dir = path_utils.hls_media_dir(self._settings, media_id)
        audio_dir = hls_dir / f"audio_{track_index}"
        audio_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = audio_dir / "playlist.m3u8"

        # Always enqueue the audio extraction job if not complete
        complete_marker = audio_dir / ".complete"
        if not complete_marker.is_file():
            task_key = f"{media_id}:audio:{track_index}"
            if task_key not in self._queued_keys and task_key not in self._active_tasks:
                await self._job_queue.put(
                    TranscodeRequest(
                        media_id=media_id,
                        source_path=source_path,
                        preset=QUALITY_PRESETS[self._settings.hls_default_quality],
                        kind=f"audio:{track_index}",
                    )
                )
                self._queued_keys.add(task_key)

        # If we already have an estimated playlist, return it immediately
        if playlist_path.is_file():
            return playlist_path

        duration = await self._get_duration(source_path)
        if duration is None:
            return None
        self._write_estimated_audio_playlist(media_id, duration, track_index)
        return playlist_path if playlist_path.is_file() else None

    async def get_audio_segment_path(
        self, media_id: str, track_index: int, segment: str, source_path: Path | None = None
    ) -> Path | None:
        audio_dir = path_utils.hls_media_dir(self._settings, media_id) / f"audio_{track_index}"
        target = audio_dir / segment

        # Handle init.mp4 for audio tracks
        if target.is_file():
            return target

        if source_path is not None:
            await self.get_audio_track_playlist(media_id, source_path, track_index)
            for _ in range(240):  # 60 seconds
                if target.is_file():
                    return target
                await asyncio.sleep(0.25)
        return target if target.is_file() else None

    async def get_subtitle_vtt(
        self, media_id: str, source_path: Path, track_index: int
    ) -> Path | None:
        hls_dir = path_utils.hls_media_dir(self._settings, media_id)
        hls_dir.mkdir(parents=True, exist_ok=True)
        vtt_path = hls_dir / f"subtitle_{track_index}.vtt"
        if vtt_path.is_file():
            return vtt_path

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source_path),
            "-map", f"0:{track_index}",
            "-c:s", "webvtt",
            "-f", "webvtt",
            str(vtt_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(
                "Subtitle extraction failed for %s track %d: %s",
                media_id, track_index,
                stderr.decode(errors="replace").strip()[-400:],
            )
            return None
        return vtt_path if vtt_path.is_file() else None

    def delete_media_cache(self, media_id: str) -> None:
        self._cleanup_hls_cache(media_id)
        ffprobe_cache = path_utils.ffprobe_cache_path(self._settings, media_id)
        if ffprobe_cache.is_file():
            ffprobe_cache.unlink(missing_ok=True)
        meta_dir = self._settings.metadata_cache_dir
        for ext in (".json", ".tmdb.json", ".ffprobe.json"):
            cache_file = meta_dir / f"{media_id}{ext}"
            if cache_file.is_file():
                cache_file.unlink(missing_ok=True)

    async def shutdown(self) -> None:
        self._shutdown = True
        for task in self._workers:
            task.cancel()
        for process in self._active_processes.values():
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        tasks = list(self._active_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def queue_snapshot(self) -> dict[str, Any]:
        return {
            "queued_jobs": self._job_queue.qsize(),
            "active_jobs": len(self._active_tasks),
            "active_keys": sorted(self._active_tasks.keys()),
        }

    def public_base_url(self) -> str:
        return self._settings.public_base_url

    def playlist_state(self, media_id: str) -> dict[str, Any]:
        manifest = self._read_media_manifest(media_id)
        return {
            "media_id": media_id,
            "manifest": manifest,
            "qualities": {
                preset.name: {
                    "ready": (path_utils.hls_quality_dir(self._settings, media_id, preset.name) / ".complete").is_file()
                }
                for preset in QUALITY_PRESETS.values()
            },
        }

    # ── Worker Loop ─────────────────────────────────────────────────────

    def _start_workers(self) -> None:
        self._workers = [
            asyncio.create_task(self._worker_loop(index))
            for index in range(self._settings.hls_max_concurrent_transcodes)
        ]

    async def _worker_loop(self, worker_index: int) -> None:
        while True:
            request = await self._job_queue.get()
            task_key = self._task_key(request)
            self._queued_keys.discard(task_key)
            task = asyncio.current_task()
            if task is not None:
                self._active_tasks[task_key] = task
            try:
                if request.kind.startswith("audio:"):
                    track_index = int(request.kind.split(":")[1])
                    await self._generate_audio_track(request.media_id, request.source_path, track_index)
                else:
                    await self._generate_variant(request.media_id, request.source_path, request.preset, request.start_segment)
                await self._emit_queue_status()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Transcode worker %d failed for %s: %s", worker_index, task_key, exc)
            finally:
                self._active_tasks.pop(task_key, None)
                self._job_queue.task_done()
                await self._emit_queue_status()

    # ── Cancel Distant Transcodes (Seek Optimization) ───────────────────

    async def _cancel_distant_transcodes(
        self, media_id: str, quality: str, target_segment: int | None
    ) -> None:
        """Kill active ffmpeg processes that are transcoding segments far away
        from *target_segment* for the same media, OR that are for a different quality,
        OR that are for a completely different media item (to free global resources)."""
        prefix = f"{media_id}:"
        seg_duration = self._settings.hls_segment_duration
        # Consider "close" as within 30 segments (~2 min of content)
        close_threshold = 30

        keys_to_cancel: list[str] = []
        for key, process in list(self._active_processes.items()):
            if not key.startswith(prefix):
                # Different media item -> Kill immediately to free global CPU/slots
                keys_to_cancel.append(key)
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                logger.info("Killed transcode for different media %s to free resources", key)
                continue

            parts = key.split(":")
            if len(parts) < 3:
                continue
            try:
                active_quality = parts[1]
                active_start = int(parts[2])
            except ValueError:
                continue

            should_kill = False
            # Kill if it's a video transcode for a DIFFERENT quality
            if active_quality != "audio" and active_quality != quality:
                should_kill = True
            # Or if it's the SAME quality but far away from the seek point
            elif target_segment is not None and abs(active_start - target_segment) > close_threshold:
                should_kill = True

            if should_kill:
                keys_to_cancel.append(key)
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                logger.info(
                    "Killed transcode %s (requested_quality=%s, target=%s) to free CPU",
                    key, quality, target_segment,
                )

        # Remove keys of cancelled processes
        for key in keys_to_cancel:
            self._active_processes.pop(key, None)

        # Also drain queued jobs that are for different media, different qualities, or far away
        new_queue: list[TranscodeRequest] = []
        while not self._job_queue.empty():
            try:
                req = self._job_queue.get_nowait()
                req_key = self._task_key(req)
                
                should_drop = False
                if req.media_id != media_id:
                    should_drop = True
                else:
                    if req.kind == "video" and req.preset.name != quality:
                        should_drop = True
                    elif target_segment is not None and abs(req.start_segment - target_segment) > close_threshold:
                        should_drop = True

                if should_drop:
                    self._queued_keys.discard(req_key)
                    logger.debug("Dropped queued job %s", req_key)
                else:
                    new_queue.append(req)
                self._job_queue.task_done()
            except asyncio.QueueEmpty:
                break
        for req in new_queue:
            await self._job_queue.put(req)

    # ── Enqueue Jobs ────────────────────────────────────────────────────

    async def _enqueue_default_jobs(self, media_id: str, source_path: Path) -> None:
        """Enqueue only the default quality for background preparation."""
        default_preset = QUALITY_PRESETS.get(
            self._settings.hls_default_quality, QUALITY_PRESETS["720p"]
        )
        await self._enqueue_video_job(media_id, source_path, default_preset)

    async def _enqueue_video_job(
        self,
        media_id: str,
        source_path: Path,
        preset: QualityPreset,
        start_segment: int = 0,
    ) -> None:
        quality_dir = path_utils.hls_quality_dir(self._settings, media_id, preset.name)
        if start_segment == 0 and (quality_dir / ".complete").is_file():
            return
        request = TranscodeRequest(media_id, source_path, preset, start_segment=start_segment)
        task_key = self._task_key(request)
        if task_key in self._queued_keys or task_key in self._active_tasks:
            return
        await self._job_queue.put(request)
        self._queued_keys.add(task_key)
        await self._emit_queue_status()

    async def _emit_queue_status(self) -> None:
        if self._metrics is not None:
            await self._metrics.set_gauge("transcode.queue_depth", self._job_queue.qsize())
            await self._metrics.set_gauge("transcode.active_jobs", len(self._active_tasks))
        if self._events is not None:
            await self._events.broadcast("encoding_queue_status")

    # ── Audio Track Generation ──────────────────────────────────────────

    async def _generate_audio_track(self, media_id: str, source_path: Path, track_index: int) -> None:
        audio_dir = path_utils.hls_media_dir(self._settings, media_id) / f"audio_{track_index}"
        audio_dir.mkdir(parents=True, exist_ok=True)
        complete_marker = audio_dir / ".complete"
        if complete_marker.is_file():
            return

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source_path),
            "-map", f"0:{track_index}",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ac", "2",
            "-vn",
            "-f", "hls",
            "-hls_segment_type", "fmp4",
            "-hls_time", str(self._settings.hls_segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_list_size", "0",
            "-hls_fmp4_init_filename", "init.mp4",
            "-hls_flags", "temp_file",
            "-hls_segment_filename", str(audio_dir / "segment_%03d.m4s"),
            str(audio_dir / "playlist.m3u8"),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        task_key = f"{media_id}:audio:{track_index}"
        self._active_processes[task_key] = process
        _, stderr = await process.communicate()
        self._active_processes.pop(task_key, None)
        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error("FFmpeg audio transcode failed. Stderr output:\n%s", err_msg)
            raise RuntimeError(err_msg[-500:])
        complete_marker.write_text("done", encoding="utf-8")

    # ── Video Variant Generation (Optimised for Speed) ──────────────────

    async def _generate_variant(
        self,
        media_id: str,
        source_path: Path,
        preset: QualityPreset,
        start_segment: int = 0,
    ) -> None:
        quality_dir = path_utils.hls_quality_dir(self._settings, media_id, preset.name)
        quality_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = quality_dir / "playlist.m3u8"
        segment_ext = "m4s" if self._settings.hls_use_cmaf else "ts"
        segment_pattern = str(quality_dir / f"segment_%03d.{segment_ext}")
        task_key = f"{media_id}:{preset.name}:{start_segment}"

        # ── Encoder selection: ultrafast for immediate playback ─────────────────
        video_encoder = [
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-profile:v", "main",
            "-sc_threshold", "0",
            "-g", str(self._settings.hls_segment_duration * 24),
            "-keyint_min", str(self._settings.hls_segment_duration * 24),
        ]

        cmd = ["ffmpeg", "-y"]
        if start_segment > 0:
            # Use -ss BEFORE -i for fast seeking (input seeking)
            cmd.extend(["-ss", str(start_segment * self._settings.hls_segment_duration)])
        cmd.extend([
            "-i", str(source_path),
            *video_encoder,
            "-map", "0:v:0",
            "-map", "0:a:0?",
            "-c:a", "aac",
            "-ac", "2",
            "-b:v", preset.video_bitrate,
            "-maxrate", preset.video_bitrate,
            "-bufsize", f"{int(preset.video_bitrate[:-1]) * 2}k",
            "-b:a", preset.audio_bitrate,
            "-vf", f"scale=-2:{preset.height}",
            "-f", "hls",
            "-hls_time", str(self._settings.hls_segment_duration),
            "-hls_playlist_type", "vod",
            "-hls_list_size", "0",
            "-hls_flags", "independent_segments+temp_file",
        ])

        if start_segment > 0:
            # Use start_number so segment filenames match what the playlist expects
            cmd.extend(["-start_number", str(start_segment)])

        if self._settings.hls_use_cmaf:
            cmd.extend([
                "-hls_segment_type", "fmp4",
                "-hls_fmp4_init_filename", "init.mp4",
            ])
        cmd.extend(["-hls_segment_filename", segment_pattern, str(playlist_path)])

        _ffmpeg_logger.debug("Generating HLS %s: %s", preset.name, " ".join(cmd))
        async with self._semaphore:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            self._active_processes[task_key] = process
            _, stderr = await process.communicate()
            self._active_processes.pop(task_key, None)

        if process.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            logger.error("FFmpeg variant transcode failed. Stderr output:\n%s", err_msg)
            raise RuntimeError(err_msg[-500:])

        self._normalize_variant_playlist(playlist_path)
        if start_segment == 0:
            (quality_dir / ".complete").write_text("done", encoding="utf-8")
        if self._metrics is not None:
            await self._metrics.incr("transcode.completed")

    # ── Prefetch ────────────────────────────────────────────────────────

    async def _maybe_prefetch(
        self,
        media_id: str,
        source_path: Path,
        preset: QualityPreset,
        segment: str,
    ) -> None:
        if not segment.startswith("segment_"):
            return
        requested_index = self._segment_index(segment)
        if requested_index < 0:
            return
        # Enqueue from start if not complete
        quality_dir = path_utils.hls_quality_dir(self._settings, media_id, preset.name)
        if not (quality_dir / ".complete").is_file():
            await self._enqueue_video_job(media_id, source_path, preset)

    # ── Audio Track Detection ───────────────────────────────────────────

    async def _detect_audio_tracks(self, source_path: Path) -> list[dict[str, Any]]:
        """Use ffprobe to detect audio tracks in the source file."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-select_streams", "a",
            str(source_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            return []
        try:
            data = json.loads(stdout.decode())
            tracks = []
            for stream in data.get("streams", []):
                tags = stream.get("tags", {})
                tracks.append({
                    "index": stream.get("index", 0),
                    "language": tags.get("language", tags.get("LANGUAGE", "und")),
                    "title": tags.get("title", tags.get("TITLE", "")),
                    "channels": stream.get("channels", 2),
                    "codec": stream.get("codec_name", ""),
                })
            return tracks
        except (json.JSONDecodeError, KeyError):
            return []

    # ── Playlist Writers ────────────────────────────────────────────────

    def _normalize_variant_playlist(self, playlist_path: Path) -> None:
        if not playlist_path.is_file():
            return
        lines = playlist_path.read_text(encoding="utf-8").splitlines()
        normalized: list[str] = []
        seen_independent = False
        seen_playlist_type = False
        for line in lines:
            if line == "#EXT-X-INDEPENDENT-SEGMENTS":
                seen_independent = True
            if line.startswith("#EXT-X-PLAYLIST-TYPE"):
                seen_playlist_type = True
            normalized.append(line)
        if not seen_playlist_type and len(normalized) > 2:
            normalized.insert(3, "#EXT-X-PLAYLIST-TYPE:VOD")
        if not seen_independent:
            normalized.insert(4, "#EXT-X-INDEPENDENT-SEGMENTS")
        playlist_path.write_text("\n".join(normalized) + "\n", encoding="utf-8")

    def _write_master_playlist(
        self,
        media_id: str,
        source_width: int | None = None,
        audio_tracks: list[dict[str, Any]] | None = None,
    ) -> None:
        """Write the HLS master playlist with proper audio renditions."""
        master_path = path_utils.hls_master_playlist_path(self._settings, media_id)
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:7",
            "#EXT-X-INDEPENDENT-SEGMENTS",
            "",
        ]

        has_multi_audio = audio_tracks and len(audio_tracks) > 1
        audio_group = "audio"

        if has_multi_audio:
            # Write EXT-X-MEDIA entries for each audio track
            for i, track in enumerate(audio_tracks):
                lang = track.get("language", "und")
                title = track.get("title", "").strip()
                name_parts = []
                
                # Build a descriptive name
                if title:
                    name_parts.append(title)
                elif lang and lang != "und":
                    name_parts.append(lang.title())
                else:
                    name_parts.append(f"Track {i + 1}")

                channels = track.get("channels", 2)
                ch_str = "6" if channels >= 6 else "2"
                track_name = " ".join(name_parts)
                is_default = "YES" if i == 0 else "NO"

                lines.append(
                     f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="{audio_group}",'
                     f'NAME="{track_name}",LANGUAGE="{lang}",'
                     f'DEFAULT={is_default},AUTOSELECT={is_default},'
                     f'CHANNELS="{ch_str}",'
                     f'URI="audio_{track["index"]}/playlist.m3u8"'
                )
            lines.append("")

        # Filter quality presets to prevent upscaling
        included_presets = []
        for preset in QUALITY_PRESETS.values():
            preset_width = preset.height * 16 // 9
            if source_width is not None and preset_width > source_width + 50:
                continue
            included_presets.append(preset)

        # Fallback to at least 240p
        if not included_presets:
            included_presets = [QUALITY_PRESETS["240p"]]

        for preset in included_presets:
            stream_inf = (
                f"#EXT-X-STREAM-INF:BANDWIDTH={preset.bandwidth},"
                f"AVERAGE-BANDWIDTH={int(preset.bandwidth * 0.85)},"
                f"RESOLUTION={self._resolution_for_preset(preset)},"
                f'CODECS="avc1.4d401f,mp4a.40.2",NAME="{preset.name}"'
            )
            if has_multi_audio:
                stream_inf += f',AUDIO="{audio_group}"'
            lines.append(stream_inf)
            lines.append(f"{preset.name}/playlist.m3u8")
        master_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_estimated_variant_playlist(
        self, media_id: str, duration_seconds: float, preset_name: str
    ) -> None:
        quality_dir = path_utils.hls_quality_dir(self._settings, media_id, preset_name)
        playlist_path = quality_dir / "playlist.m3u8"
        if playlist_path.is_file():
            return
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:7",
            f"#EXT-X-TARGETDURATION:{self._settings.hls_segment_duration}",
            "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD",
            "#EXT-X-INDEPENDENT-SEGMENTS",
        ]
        if self._settings.hls_use_cmaf:
            lines.append('#EXT-X-MAP:URI="init.mp4"')

        num_segments = int(duration_seconds // self._settings.hls_segment_duration)
        remainder = duration_seconds % self._settings.hls_segment_duration
        segment_ext = "m4s" if self._settings.hls_use_cmaf else "ts"
        for idx in range(num_segments):
            lines.append(f"#EXTINF:{self._settings.hls_segment_duration:.6f},")
            lines.append(f"segment_{idx:03d}.{segment_ext}")
        if remainder > 0.001:
            lines.append(f"#EXTINF:{remainder:.6f},")
            lines.append(f"segment_{num_segments:03d}.{segment_ext}")
        lines.append("#EXT-X-ENDLIST")
        playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_estimated_audio_playlist(
        self, media_id: str, duration_seconds: float, track_index: int
    ) -> None:
        """Write an estimated audio playlist so HLS.js can start immediately."""
        audio_dir = path_utils.hls_media_dir(self._settings, media_id) / f"audio_{track_index}"
        audio_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = audio_dir / "playlist.m3u8"
        if playlist_path.is_file():
            return

        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:7",
            f"#EXT-X-TARGETDURATION:{self._settings.hls_segment_duration}",
            "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD",
            "#EXT-X-INDEPENDENT-SEGMENTS",
            '#EXT-X-MAP:URI="init.mp4"',
        ]

        num_segments = int(duration_seconds // self._settings.hls_segment_duration)
        remainder = duration_seconds % self._settings.hls_segment_duration
        for idx in range(num_segments):
            lines.append(f"#EXTINF:{self._settings.hls_segment_duration:.6f},")
            lines.append(f"segment_{idx:03d}.m4s")
        if remainder > 0.001:
            lines.append(f"#EXTINF:{remainder:.6f},")
            lines.append(f"segment_{num_segments:03d}.m4s")
        lines.append("#EXT-X-ENDLIST")
        playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_media_manifest(self, media_id: str, source_path: Path, duration: float) -> None:
        manifest_path = path_utils.hls_media_dir(self._settings, media_id) / "manifest.json"
        payload = {
            "media_id": media_id,
            "source_mtime_ns": source_path.stat().st_mtime_ns,
            "duration_seconds": duration,
            "segment_duration": self._settings.hls_segment_duration,
            "segment_type": "fmp4" if self._settings.hls_use_cmaf else "mpegts",
            "generated_at": int(time.time()),
        }
        manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_media_manifest(self, media_id: str) -> dict[str, Any] | None:
        manifest_path = path_utils.hls_media_dir(self._settings, media_id) / "manifest.json"
        if not manifest_path.is_file():
            return None
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    async def _get_duration(self, source_path: Path) -> float | None:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(source_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            return None
        try:
            return float(stdout.decode().strip())
        except ValueError:
            return None

    def _is_stale(self, media_id: str, source_path: Path) -> bool:
        manifest = self._read_media_manifest(media_id)
        if manifest is None:
            return True
        return int(manifest.get("source_mtime_ns", 0)) != source_path.stat().st_mtime_ns

    def _cleanup_hls_cache(self, media_id: str) -> None:
        prefix = f"{media_id}:"
        for key, process in list(self._active_processes.items()):
            if key.startswith(prefix):
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                self._active_processes.pop(key, None)
        hls_dir = path_utils.hls_media_dir(self._settings, media_id)
        if hls_dir.is_dir():
            shutil.rmtree(hls_dir, ignore_errors=True)

    def _cleanup_stale_caches(self) -> None:
        cutoff = time.time() - self._settings.hls_stale_cleanup_age_seconds
        root = self._settings.hls_cache_dir
        if not root.is_dir():
            return
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            manifest_path = entry / "manifest.json"
            if not manifest_path.is_file():
                shutil.rmtree(entry, ignore_errors=True)
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if float(manifest.get("generated_at", 0)) < cutoff:
                    shutil.rmtree(entry, ignore_errors=True)
            except Exception:
                shutil.rmtree(entry, ignore_errors=True)

    def _segment_index(self, segment_name: str) -> int:
        stem = Path(segment_name).stem
        if "_" not in stem:
            return 0
        _, _, suffix = stem.partition("_")
        return int(suffix) if suffix.isdigit() else 0

    def _task_key(self, request: TranscodeRequest) -> str:
        if request.kind != "video":
            return f"{request.media_id}:{request.kind}"
        return f"{request.media_id}:{request.preset.name}:{request.start_segment}"

    @staticmethod
    def _resolution_for_preset(preset: QualityPreset) -> str:
        width = preset.height * 16 // 9
        if width % 2:
            width += 1
        return f"{width}x{preset.height}"

    async def _get_video_width(self, source_path: Path) -> int | None:
        """Use ffprobe to detect the width of the source video."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(source_path),
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await process.communicate()
        if process.returncode != 0:
            return None
        try:
            return int(stdout.decode().strip())
        except ValueError:
            return None
