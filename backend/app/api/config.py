from __future__ import annotations

import json
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.dependencies import SettingsDep, TunnelServiceDep

router = APIRouter(tags=["config"])


class NameRequest(BaseModel):
    name: str


class NameResponse(BaseModel):
    name: str
    tunnel_public_url: str = ""
    websocket_path: str = "/api/v1/ws"
    tunnel_provider: str = "none"


def get_config_file_path(settings: SettingsDep) -> Path:
    return settings.cache_root / "config.json"


@router.get("/name", response_model=NameResponse)
async def get_name(
    settings: SettingsDep,
    tunnel_service: TunnelServiceDep,
) -> NameResponse:
    path = get_config_file_path(settings)
    name = "Paras"
    if path.is_file():
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as fh:
                data = json.loads(await fh.read())
            name = str(data.get("name", name))
        except Exception:
            pass
    tunnel_state = tunnel_service.state()
    return NameResponse(
        name=name,
        tunnel_public_url=tunnel_state.public_url,
        websocket_path=f"{settings.api_prefix}/ws",
        tunnel_provider=tunnel_state.provider,
    )


@router.post("/name", response_model=NameResponse)
async def set_name(
    req: NameRequest,
    request: Request,
    settings: SettingsDep,
    tunnel_service: TunnelServiceDep,
) -> NameResponse:
    path = get_config_file_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as fh:
        await fh.write(json.dumps({"name": req.name}))
    request.app.title = "StreamHug"
    tunnel_state = tunnel_service.state()
    return NameResponse(
        name=req.name,
        tunnel_public_url=tunnel_state.public_url,
        websocket_path=f"{settings.api_prefix}/ws",
        tunnel_provider=tunnel_state.provider,
    )


@router.get("/runtime")
async def get_runtime_config(
    settings: SettingsDep,
    tunnel_service: TunnelServiceDep,
) -> dict[str, object]:
    tunnel_state = tunnel_service.state()
    return {
        "api_prefix": settings.api_prefix,
        "public_base_url": settings.public_base_url or tunnel_state.public_url,
        "tunnel": tunnel_state.as_dict(),
        "streaming": {
            "segment_duration": settings.hls_segment_duration,
            "default_quality": settings.hls_default_quality,
            "use_cmaf": settings.hls_use_cmaf,
        },
        "websocket": {
            "enabled": settings.websocket_enabled,
            "path": f"{settings.api_prefix}/ws",
            "heartbeat_seconds": settings.websocket_heartbeat_seconds,
        },
        "auth": {
            "enabled": settings.auth_enabled,
            "signin_path": f"{settings.api_prefix}/auth/signin",
            "signup_path": f"{settings.api_prefix}/auth/signup",
            "verify_path": f"{settings.api_prefix}/auth/verify",
            "verification_delivery": settings.auth_verification_delivery,
        },
    }
