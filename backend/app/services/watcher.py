"""Media directory watcher.

Watches media/originals for filesystem changes and reacts:
  - On CREATE/MODIFY of a video file: triggers a library rescan, then
    immediately starts background HLS pre-transcoding for new items.
  - On DELETE of a video file: deletes all associated caches and rescans.
"""

import asyncio
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from app.core.logging_config import get_logger
from app.services.scanner import ScannerService
from app.services.events import EventService
from app.services.hls import HLSService
from app.services.library import LibraryService
from app.utils.media_identity import generate_media_id
from app.utils.paths import is_video_file

logger = get_logger("watcher")


class MediaWatcher(FileSystemEventHandler):
    """Watches the media directory for changes and triggers rescans and transcoding."""

    def __init__(
        self,
        media_root: Path,
        scanner_service: ScannerService,
        event_service: EventService,
        hls_service: HLSService,
        library_service: LibraryService,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self.media_root = media_root
        self.scanner_service = scanner_service
        self.event_service = event_service
        self.hls_service = hls_service
        self.library_service = library_service
        self.loop = loop

        self.observer = Observer()
        self._debouncer: asyncio.TimerHandle | None = None
        self._scan_delay = 3.0  # wait for file copy to complete
        # Queue of (path, event_type) to handle on next scan cycle
        self._pending_deletes: list[Path] = []
        self._pending_creates: list[Path] = []

    def start(self) -> None:
        """Start watching the media directory."""
        if not self.media_root.exists():
            return
        self.observer.schedule(self, str(self.media_root), recursive=True)
        self.observer.start()
        logger.info("Started watching %s for changes", self.media_root)

    def stop(self) -> None:
        """Stop watching."""
        self.observer.stop()
        self.observer.join()
        logger.info("Stopped watching media directory")

    def _is_video_file_path(self, path: str) -> bool:
        p = Path(path)
        return is_video_file(p)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if not self._is_video_file_path(event.src_path):
            return
        logger.debug("File created: %s", event.src_path)
        self.loop.call_soon_threadsafe(
            self._queue_create, Path(event.src_path)
        )

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if not self._is_video_file_path(event.src_path):
            return
        logger.debug("File modified: %s", event.src_path)
        self.loop.call_soon_threadsafe(
            self._queue_create, Path(event.src_path)
        )

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        if not self._is_video_file_path(event.src_path):
            return
        logger.info("File deleted: %s — purging cache", event.src_path)
        self.loop.call_soon_threadsafe(
            self._queue_delete, Path(event.src_path)
        )

    def _queue_create(self, path: Path) -> None:
        if path not in self._pending_creates:
            self._pending_creates.append(path)
        self._schedule_scan()

    def _queue_delete(self, path: Path) -> None:
        if path not in self._pending_deletes:
            self._pending_deletes.append(path)
        self._schedule_scan()

    def _schedule_scan(self) -> None:
        if self._debouncer is not None:
            self._debouncer.cancel()
        self._debouncer = self.loop.call_later(self._scan_delay, self._execute_scan)

    def _execute_scan(self) -> None:
        self._debouncer = None
        asyncio.create_task(self._async_scan_and_notify())

    async def _async_scan_and_notify(self) -> None:
        """Rescan the library, handle deletes, then auto-transcode new files."""
        logger.info("Triggering automatic media scan due to file changes...")

        # Handle pending deletions BEFORE the rescan
        pending_deletes = self._pending_deletes[:]
        self._pending_deletes.clear()
        for deleted_path in pending_deletes:
            try:
                media_id = generate_media_id(deleted_path)
                self.hls_service.delete_media_cache(media_id)
                logger.info("Auto-purged cache for deleted file: %s", deleted_path.name)
            except Exception as exc:
                logger.error("Failed to purge cache for %s: %s", deleted_path.name, exc)

        # Capture current library IDs before rescan
        ids_before: set[str] = set(self.library_service.all_media_ids())

        pending_creates = self._pending_creates[:]
        self._pending_creates.clear()

        try:
            await self.scanner_service.scan()
            await self.event_service.broadcast("library_updated")
            logger.info("Automatic scan complete, clients notified.")
        except Exception:
            logger.exception("Failed automatic scan")
            return

        # Detect newly added media and kick off HLS pre-transcoding
        ids_after: set[str] = set(self.library_service.all_media_ids())
        new_ids = ids_after - ids_before

        if new_ids:
            logger.info("Auto-transcoding %d new media item(s)...", len(new_ids))
            for media_id in new_ids:
                source_path = self.library_service.get_file_path_for_id(media_id)
                if source_path and source_path.is_file():
                    try:
                        await self.hls_service.start_early_transcoding(media_id, source_path)
                        logger.info("Started early pre-transcoding for: %s (%s)", media_id, source_path.name)
                    except Exception as exc:
                        logger.error("Failed to start early pre-transcoding for %s: %s", media_id, exc)
