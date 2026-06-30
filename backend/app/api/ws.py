"""Realtime WebSocket endpoints for playback and transcoding state."""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.dependencies import AuthServiceDep, MetricsServiceDep, WebSocketManagerDep
from app.services.auth import AuthError

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    websocket_manager: WebSocketManagerDep,
    metrics_service: MetricsServiceDep,
    auth_service: AuthServiceDep,
    token: str = Query(default=""),
    topics: str = Query(default="playback,notifications,queue"),
) -> None:
    settings = websocket.app.state.settings
    user_id = "anonymous"
    if settings.websocket_auth_token and token == settings.websocket_auth_token:
        user_id = "legacy-websocket-client"
    elif token:
        try:
            current_user = await auth_service.get_user_from_access_token(token)
            user_id = current_user.user_id
        except AuthError:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return
    elif settings.websocket_auth_token and token != settings.websocket_auth_token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    client = await websocket_manager.connect(
        websocket,
        token=token,
        topics={part.strip() for part in topics.split(",") if part.strip()},
        user_id=user_id,
    )
    await metrics_service.incr("websocket.accepted")
    try:
        while True:
            payload = await websocket.receive_json()
            await websocket_manager.handle_message(client, payload)
    except WebSocketDisconnect:
        await websocket_manager.disconnect(client.client_id)
    except Exception:
        await websocket_manager.disconnect(client.client_id)
        raise
