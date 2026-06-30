import asyncio
from collections.abc import Awaitable, Callable
from typing import AsyncGenerator


class EventService:
    """Manages Server-Sent Events (SSE) broadcasting to connected clients."""

    def __init__(self) -> None:
        self._queues: list[asyncio.Queue[str]] = []
        self._listeners: list[Callable[[str], Awaitable[None]]] = []

    async def connect(self) -> AsyncGenerator[str, None]:
        """Create a new queue for a connecting client and yield events."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            if queue in self._queues:
                self._queues.remove(queue)

    async def broadcast(self, event: str) -> None:
        """Broadcast an event string to all connected clients."""
        for queue in self._queues:
            # We use put_nowait to not block if a queue is full.
            # If it's full, the client is probably too slow, we can just drop the event or let it crash.
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
        for listener in self._listeners:
            await listener(event)

    def add_listener(self, listener: Callable[[str], Awaitable[None]]) -> None:
        self._listeners.append(listener)
