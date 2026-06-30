"""FastAPI dependency injection providers.

Each provider function reads a service singleton from ``app.state``
(populated during lifespan) and returns it as a typed dependency.
Routers use these via ``Depends()`` for clean, testable injection.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request

from app.cache.manager import CacheManager
from app.core.config import Settings
from app.services.artwork import ArtworkService
from app.services.auth import AuthError, AuthService
from app.services.ffprobe.runner import FFprobeService
from app.services.hls import HLSService
from app.services.library import LibraryService
from app.services.metrics import MetricsService
from app.services.metadata import MetadataService
from app.services.scanner import ScannerService
from app.services.events import EventService
from app.services.tunnel import TunnelService
from app.services.websocket import WebSocketManager
from app.models.auth import UserProfile


def _get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def _get_cache_manager(request: Request) -> CacheManager:
    return request.app.state.cache_manager  # type: ignore[no-any-return]


def _get_ffprobe_service(request: Request) -> FFprobeService:
    return request.app.state.ffprobe_service  # type: ignore[no-any-return]


def _get_metadata_service(request: Request) -> MetadataService:
    return request.app.state.metadata_service  # type: ignore[no-any-return]


def _get_artwork_service(request: Request) -> ArtworkService:
    return request.app.state.artwork_service  # type: ignore[no-any-return]


def _get_hls_service(request: Request) -> HLSService:
    return request.app.state.hls_service  # type: ignore[no-any-return]


def _get_library_service(request: Request) -> LibraryService:
    return request.app.state.library_service  # type: ignore[no-any-return]


def _get_scanner_service(request: Request) -> ScannerService:
    return request.app.state.scanner_service  # type: ignore[no-any-return]


def _get_event_service(request: Request) -> EventService:
    return request.app.state.event_service  # type: ignore[no-any-return]


def _get_metrics_service(request: Request) -> MetricsService:
    return request.app.state.metrics_service  # type: ignore[no-any-return]


def _get_tunnel_service(request: Request) -> TunnelService:
    return request.app.state.tunnel_service  # type: ignore[no-any-return]


def _get_websocket_manager(request: Request) -> WebSocketManager:
    return request.app.state.websocket_manager  # type: ignore[no-any-return]


def _get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service  # type: ignore[no-any-return]


async def _get_current_user(
    auth_service: Annotated[AuthService, Depends(_get_auth_service)],
    authorization: Annotated[str | None, Header()] = None,
) -> UserProfile:
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        return await auth_service.get_user_from_access_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


async def _get_current_admin(
    current_user: Annotated[UserProfile, Depends(_get_current_user)],
) -> UserProfile:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ── Annotated type aliases for use in router signatures ──────────────────

SettingsDep = Annotated[Settings, Depends(_get_settings)]
CacheManagerDep = Annotated[CacheManager, Depends(_get_cache_manager)]
FFprobeServiceDep = Annotated[FFprobeService, Depends(_get_ffprobe_service)]
MetadataServiceDep = Annotated[MetadataService, Depends(_get_metadata_service)]
ArtworkServiceDep = Annotated[ArtworkService, Depends(_get_artwork_service)]
HLSServiceDep = Annotated[HLSService, Depends(_get_hls_service)]
LibraryServiceDep = Annotated[LibraryService, Depends(_get_library_service)]
ScannerServiceDep = Annotated[ScannerService, Depends(_get_scanner_service)]
EventServiceDep = Annotated[EventService, Depends(_get_event_service)]
MetricsServiceDep = Annotated[MetricsService, Depends(_get_metrics_service)]
TunnelServiceDep = Annotated[TunnelService, Depends(_get_tunnel_service)]
WebSocketManagerDep = Annotated[WebSocketManager, Depends(_get_websocket_manager)]
AuthServiceDep = Annotated[AuthService, Depends(_get_auth_service)]
CurrentUserDep = Annotated[UserProfile, Depends(_get_current_user)]
CurrentAdminDep = Annotated[UserProfile, Depends(_get_current_admin)]
