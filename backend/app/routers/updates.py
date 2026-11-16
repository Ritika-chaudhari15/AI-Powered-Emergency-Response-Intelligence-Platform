import asyncio
from queue import Empty, Queue

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user
from app.models import User
from app.services import live_update_service


router = APIRouter(prefix="/api/v1/updates", tags=["Live updates"])


@router.get("/stream")
async def stream_updates(user: User = Depends(get_current_user)):
    """Authenticated Server-Sent Events stream; clients receive lifecycle and notification events."""
    queue: Queue = live_update_service.subscribe(user.id)

    async def event_stream():
        try:
            yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
            while True:
                try:
                    message = await asyncio.to_thread(queue.get, True, 15)
                    yield f"event: update\ndata: {message}\n\n"
                except Empty:
                    yield ": keep-alive\n\n"
        finally:
            live_update_service.unsubscribe(user.id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
