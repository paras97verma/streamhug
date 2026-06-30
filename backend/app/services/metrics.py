"""Lightweight in-process metrics and telemetry collection."""

from __future__ import annotations

import asyncio
import time
from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass(slots=True)
class PlaybackSnapshot:
    media_id: str
    position_seconds: float
    updated_at: float


class MetricsService:
    """Collects low-overhead counters and gauges for operational visibility."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counters: Counter[str] = Counter()
        self._gauges: dict[str, float] = defaultdict(float)
        self._playback: dict[str, PlaybackSnapshot] = {}

    async def incr(self, name: str, value: int = 1) -> None:
        async with self._lock:
            self._counters[name] += value

    async def set_gauge(self, name: str, value: float) -> None:
        async with self._lock:
            self._gauges[name] = value

    async def track_playback(
        self, client_id: str, media_id: str, position_seconds: float
    ) -> None:
        async with self._lock:
            self._playback[client_id] = PlaybackSnapshot(
                media_id=media_id,
                position_seconds=position_seconds,
                updated_at=time.time(),
            )

    async def clear_playback(self, client_id: str) -> None:
        async with self._lock:
            self._playback.pop(client_id, None)

    async def snapshot(self) -> dict[str, object]:
        async with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "active_playback_clients": len(self._playback),
                "playback": {
                    key: {
                        "media_id": item.media_id,
                        "position_seconds": item.position_seconds,
                        "updated_at": item.updated_at,
                    }
                    for key, item in self._playback.items()
                },
            }

    async def render_prometheus(self) -> str:
        snapshot = await self.snapshot()
        lines = [
            "# HELP streamhug_active_playback_clients Number of active playback clients.",
            "# TYPE streamhug_active_playback_clients gauge",
            f"streamhug_active_playback_clients {snapshot['active_playback_clients']}",
        ]
        for name, value in sorted(snapshot["gauges"].items()):
            metric = name.replace(".", "_")
            lines.append(f"# TYPE streamhug_{metric} gauge")
            lines.append(f"streamhug_{metric} {value}")
        for name, value in sorted(snapshot["counters"].items()):
            metric = name.replace(".", "_")
            lines.append(f"# TYPE streamhug_{metric} counter")
            lines.append(f"streamhug_{metric} {value}")
        return "\n".join(lines) + "\n"
