"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import LibraryServiceDep, SettingsDep, TunnelServiceDep
from app.models.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
)
async def health_check(
    library_service: LibraryServiceDep,
    settings: SettingsDep,
    tunnel_service: TunnelServiceDep,
) -> HealthResponse:
    """Return the current health status of the StreamHug server."""
    tunnel_state = tunnel_service.state()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        media_count=library_service.count,
        tunnel_public_url=tunnel_state.public_url,
        websocket_enabled=settings.websocket_enabled,
        redis_enabled=bool(settings.redis_url),
    )


@router.get("/ready", summary="Readiness probe")
async def readiness_check(tunnel_service: TunnelServiceDep) -> dict[str, object]:
    tunnel_state = tunnel_service.state()
    return {
        "ready": True,
        "tunnel_connected": tunnel_state.connected or not tunnel_state.enabled,
        "tunnel_public_url": tunnel_state.public_url,
    }
