from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import EventServiceDep

router = APIRouter(tags=["events"])


@router.get("/events")
async def sse_events(request: Request, event_service: EventServiceDep):
    """Subscribe to server-sent events for real-time updates."""

    async def event_generator():
        # Yield events from the service's connect generator
        async for event in event_service.connect():
            # If client disconnects, we should stop
            if await request.is_disconnected():
                break
            yield {"event": event, "data": ""}

    return EventSourceResponse(event_generator())
