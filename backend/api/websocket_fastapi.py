"""
Socket.IO ASGI app for the accessible interface.

This mirrors the behaviour of the existing Flask-SocketIO app in
`backend/api/websocket_utils.py`, but runs in ASGI mode so it can be mounted
into the FastAPI app at `/accessible-socket.io`.

Exposes:
- `socketio_app`: ASGI application to mount
- `emit_status_update_accessible(session_id, status, message)`: helper used by
  other parts of the codebase to push status updates to a specific session/room.
"""

import asyncio
import os
from typing import Any, Dict

import socketio

from backend.logger.logger import TaskLogger
from backend.config.constants import FIELD_CATEGORIES_MAPPING

task_logger = TaskLogger(service_name="socketio_fastapi")
logger = task_logger.logger

# Match Redis configuration from the Flask Socket.IO setup
SOCKETIO_REDIS_URL = os.getenv("SOCKETIO_REDIS_URL", "redis://localhost:6379/0")
logger.debug(
    "Initializing ASGI Socket.IO with Redis",
    extra={"redis_url": SOCKETIO_REDIS_URL},
)


def _build_emit_key(message: Any) -> str:
    """
    Compute the event name (emit key) based on the message content, matching
    the logic in `websocket_utils.emit_status_update_accessible`.
    """
    emit_key = "status_update"
    if isinstance(message, dict):
        if "operation" in message:
            operation = message["operation"]
            emit_key = f"status_update:{operation}"
        else:
            for k in message.keys():
                operation = FIELD_CATEGORIES_MAPPING.get(k)
                if operation:
                    emit_key = f"status_update:{operation}"
                    break
    return emit_key


# Use Redis manager so multiple workers can share the same message queue
manager = socketio.AsyncRedisManager(SOCKETIO_REDIS_URL)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    client_manager=manager,
    ping_timeout=3600,
    ping_interval=25_000,
)

# IMPORTANT: socketio_path is "accessible-socket.io" so the final path
# `/accessible-socket.io` matches what nginx/clients expect when this app
# is mounted at root or at the same prefix.
socketio_app = socketio.ASGIApp(sio, socketio_path="accessible-socket.io")


@sio.event
async def connect(sid, environ):
    logger.debug("ASGI Socket.IO client connected", extra={"sid": sid})
    logger.debug("ASGI environ keys", extra={"keys": list(environ.keys())})


@sio.event
async def disconnect(sid):
    logger.debug("ASGI Socket.IO client disconnected", extra={"sid": sid})


@sio.event
async def join(sid, data):
    room = (data or {}).get("room")
    if room:
        logger.debug("ASGI client joining room", extra={"sid": sid, "room": room})
        await sio.enter_room(sid, room)
        logger.debug("ASGI client joined room", extra={"sid": sid, "room": room})


@sio.event
async def status_update(sid, data):
    """
    Generic status_update handler. In practice most updates are emitted from
    the backend; this exists mainly for parity and debug logging.
    """
    logger.debug("ASGI status_update received", extra={"sid": sid, "data": data})


@sio.event
async def another_event(sid, data):
    logger.debug("ASGI another_event received", extra={"sid": sid, "data": data})


@sio.event
async def join_room(sid, data):
    room = (data or {}).get("room")
    if room:
        logger.debug("ASGI join_room called", extra={"sid": sid, "room": room})
        await sio.enter_room(sid, room)


def emit_status_update_accessible(session_id: str, status: str, message: Dict[str, Any]) -> None:
    """
    Fire-and-forget helper to emit a status update to a specific session/room.

    Signature matches the Flask version so existing callers can import it
    without changes. Internally this schedules an async emit on the running
    event loop.
    """

    async def _emit() -> None:
        try:
            emit_key = _build_emit_key(message)
            logger.debug(
                "ASGI emitting status update",
                extra={
                    "session_id": session_id,
                    "status": status,
                    "message": message,
                    "emit_key": emit_key,
                    "redis_url": SOCKETIO_REDIS_URL,
                },
            )
            await sio.emit(
                emit_key,
                {"status": status, "message": message, "session_id": session_id},
                room=session_id,
            )
            logger.debug(
                "ASGI status update emitted successfully",
                extra={"session_id": session_id, "emit_key": emit_key},
            )
        except Exception as e:  # pragma: no cover - defensive logging
            logger.error(
                "ASGI failed to emit status update",
                extra={"session_id": session_id, "error": str(e)},
                exc_info=True,
            )

    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_emit())
    except RuntimeError:
        # No running loop (e.g. called in a non-async context); create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_emit())

