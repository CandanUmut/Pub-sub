"""FastAPI broker: owns the connection state and the set of SSE subscribers.

This single process is the only source of truth. GUI panels never share
in-memory state with each other; every action flows through this broker over
HTTP (polling / publisher actions) or SSE (pub/sub events).
"""

import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="Pub/Sub + Polling Broker")

# Module-level state. Single uvicorn worker + asyncio is single-threaded, so
# plain module globals are safe without locks.
connection_state: str = "DISCONNECTED"
subscribers: "set[asyncio.Queue]" = set()


def _emit(message: str) -> None:
    """Push a message into every currently-subscribed queue (emit-on-press).

    A client that never opened /events has no queue here, so it receives
    nothing. This is what gates push delivery on subscription (R3.1).
    """
    for queue in subscribers:
        queue.put_nowait(message)


@app.get("/")
async def health():
    return {"status": "ok", "state": connection_state, "subscribers": len(subscribers)}


@app.get("/status")
async def status():
    """Polling endpoint: returns current state only. Never touches subscribers."""
    return {"state": connection_state}


@app.post("/connect")
async def connect():
    global connection_state
    connection_state = "CONNECTED"
    _emit("Connected")  # emit-on-press: always emits, even if already connected
    return {"state": connection_state}


@app.post("/disconnect")
async def disconnect():
    global connection_state
    connection_state = "DISCONNECTED"
    _emit("Disconnected")
    return {"state": connection_state}


@app.get("/events")
async def events():
    """SSE stream. Subscribe = open this stream; Unsubscribe = close it.

    A fresh queue is created per stream with no pre-loaded history (no replay).
    On disconnect/unsubscribe the queue is dropped from `subscribers` so no
    further events are delivered to it.
    """
    queue: asyncio.Queue = asyncio.Queue()
    subscribers.add(queue)

    async def event_generator():
        try:
            while True:
                try:
                    # Wait for an event, but wake periodically to send a
                    # heartbeat so a closed client connection is detected.
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
