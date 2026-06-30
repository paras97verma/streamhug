"""FastAPI lifespan context manager.

Handles application startup and shutdown:
  - Initialises logging
  - Validates configuration
  - Creates singleton services and stores them on ``app.state``
  - Triggers the initial media scan
  - Starts the background periodic scanner
  - Cleans up on shutdown
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.cache.manager import CacheManager
from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger, setup_logging
from app.services.artwork import ArtworkService
from app.services.auth import AuthService
from app.services.ffprobe.runner import FFprobeService
from app.services.hls import HLSService
from app.services.library import LibraryService
from app.services.metrics import MetricsService
from app.services.metadata import MetadataService
from app.services.scanner import ScannerService
from app.services.events import EventService
from app.services.tunnel import TunnelService
from app.services.watcher import MediaWatcher
from app.services.websocket import WebSocketManager

logger = get_logger("lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan managing startup / shutdown sequences.

    All service singletons are attached to ``app.state`` so they can be
    resolved via the dependency providers in ``app.core.dependencies``.
    """
    settings = get_settings()

    app.title = "StreamHug"

    # ── Logging ──────────────────────────────────────────────────────────
    setup_logging(settings.log_dir, debug=settings.debug)
    logger.info("StreamHug starting up")

    # ── Startup validation ───────────────────────────────────────────────
    warnings = settings.validate_startup()
    for warning in warnings:
        logger.warning("Startup check: %s", warning)

    # ── Service construction ─────────────────────────────────────────────
    cache_manager = CacheManager(settings)
    await cache_manager.connect()
    auth_service = AuthService(settings)
    await auth_service.initialize()
    ffprobe_service = FFprobeService(settings, cache_manager)
    metadata_service = MetadataService(settings, cache_manager)
    artwork_service = ArtworkService(settings, metadata_service)
    metrics_service = MetricsService()
    event_service = EventService()
    websocket_manager = WebSocketManager(settings, metrics_service)
    hls_service = HLSService(
        settings=settings,
        event_service=event_service,
        metrics_service=metrics_service,
    )
    library_service = LibraryService()
    scanner_service = ScannerService(
        settings=settings,
        ffprobe_service=ffprobe_service,
        metadata_service=metadata_service,
        artwork_service=artwork_service,
        library_service=library_service,
        cache_manager=cache_manager,
        hls_service=hls_service,
    )
    tunnel_service = TunnelService(settings)
    event_service.add_listener(websocket_manager.broadcast_notification)
    
    media_watcher = MediaWatcher(
        media_root=settings.media_root,
        scanner_service=scanner_service,
        event_service=event_service,
        hls_service=hls_service,
        library_service=library_service,
        loop=asyncio.get_running_loop(),
    )

    # ── Store on app.state for dependency resolution ─────────────────────
    app.state.settings = settings
    app.state.cache_manager = cache_manager
    app.state.ffprobe_service = ffprobe_service
    app.state.auth_service = auth_service
    app.state.metadata_service = metadata_service
    app.state.artwork_service = artwork_service
    app.state.hls_service = hls_service
    app.state.library_service = library_service
    app.state.scanner_service = scanner_service
    app.state.event_service = event_service
    app.state.metrics_service = metrics_service
    app.state.tunnel_service = tunnel_service
    app.state.websocket_manager = websocket_manager

    # ── Initial scan ─────────────────────────────────────────────────────
    if settings.scan_on_startup:
        logger.info("Starting initial media scan")
        await scanner_service.scan()
        logger.info("Initial scan complete — %d media items", library_service.count)

    # ── Start Watcher ────────────────────────────────────────────────────
    media_watcher.start()
    await websocket_manager.start()
    await tunnel_service.start()

    # ── Yield control to the application ─────────────────────────────────
    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("StreamHug shutting down")
    media_watcher.stop()
    await tunnel_service.stop()
    await websocket_manager.stop()
    await hls_service.shutdown()

    await auth_service.close()
    await metadata_service.close()
    await cache_manager.close()
    logger.info("Shutdown complete")
