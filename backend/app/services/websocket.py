"""Production-oriented WebSocket connection management."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.core.config import Settings
from app.core.logging_config import get_logger
from app.services.metrics import MetricsService

logger = get_logger("websocket")


@dataclass(slots=True)
class WebSocketClient:
    client_id: str
    websocket: WebSocket
    subscribed_topics: set[str] = field(default_factory=set)
    last_pong_at: float = field(default_factory=time.time)
    user_id: str = "anonymous"


class WebSocketManager:
    """Tracks client connections, heartbeats, and topic-based broadcasts."""

    def __init__(self, settings: Settings, metrics: MetricsService) -> None:
        self._settings = settings
        self._metrics = metrics
        self._clients: dict[str, WebSocketClient] = {}
        self._topics: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None

        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
            self._topics.clear()

        for client in clients:
            with contextlib.suppress(Exception):
                await client.websocket.close(code=1001, reason="Server shutdown")

    async def connect(
        self,
        websocket: WebSocket,
        *,
        token: str = "",
        topics: set[str] | None = None,
        user_id: str = "anonymous",
    ) -> WebSocketClient:
        await websocket.accept()
        client = WebSocketClient(
            client_id=uuid.uuid4().hex,
            websocket=websocket,
            subscribed_topics=topics or set(),
            user_id=user_id,
        )
        async with self._lock:
            self._clients[client.client_id] = client
            for topic in client.subscribed_topics:
                self._topics[topic].add(client.client_id)
        await self._metrics.incr("websocket.connections")
        await self._metrics.set_gauge("websocket.active_connections", len(self._clients))
        await websocket.send_json(
            {
                "type": "welcome",
                "client_id": client.client_id,
                "heartbeat_seconds": self._settings.websocket_heartbeat_seconds,
                "authenticated": bool(token),
                "reconnect": True,
            }
        )
        return client

    async def disconnect(self, client_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(client_id, None)
            if client is None:
                return
            for topic in client.subscribed_topics:
                self._topics[topic].discard(client_id)
        await self._metrics.set_gauge("websocket.active_connections", len(self._clients))
        await self._metrics.clear_playback(client_id)

    async def broadcast(
        self, topic: str, payload: dict[str, Any], *, include_all: bool = False
    ) -> None:
        async with self._lock:
            if include_all:
                targets = list(self._clients.values())
            else:
                client_ids = list(self._topics.get(topic, set()))
                targets = [
                    self._clients[client_id]
                    for client_id in client_ids
                    if client_id in self._clients
                ]

        message = json.dumps({"topic": topic, "payload": payload})
        stale: list[str] = []
        for client in targets:
            try:
                await client.websocket.send_text(message)
            except Exception:
                stale.append(client.client_id)
        for client_id in stale:
            await self.disconnect(client_id)

    async def broadcast_notification(self, event_name: str) -> None:
        await self.broadcast(
            "notifications",
            {"event": event_name, "ts": time.time()},
            include_all=True,
        )

    async def handle_message(self, client: WebSocketClient, data: dict[str, Any]) -> None:
        event_type = str(data.get("type", "")).lower()
        if event_type == "pong":
            client.last_pong_at = time.time()
            return
        if event_type == "ping":
            await client.websocket.send_json({"type": "pong", "ts": time.time()})
            client.last_pong_at = time.time()
            return
        if event_type == "subscribe":
            topics = {str(item) for item in data.get("topics", [])}
            async with self._lock:
                for topic in topics:
                    client.subscribed_topics.add(topic)
                    self._topics[topic].add(client.client_id)
            return
        if event_type == "playback_progress":
            media_id = str(data.get("media_id", ""))
            position = float(data.get("position_seconds", 0.0))
            if media_id:
                await self._metrics.track_playback(client.client_id, media_id, position)

    async def _heartbeat_loop(self) -> None:
        interval = self._settings.websocket_heartbeat_seconds
        while True:
            await asyncio.sleep(interval)
            now = time.time()
            async with self._lock:
                clients = list(self._clients.values())
            for client in clients:
                if now - client.last_pong_at > interval * 2:
                    await self.disconnect(client.client_id)
                    with contextlib.suppress(Exception):
                        await client.websocket.close(code=1001, reason="Heartbeat timeout")
                    continue
                with contextlib.suppress(Exception):
                    await client.websocket.send_json({"type": "ping", "ts": now})
