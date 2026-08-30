"""WebSocket endpoints: /ws/monitor and /ws/logs.

Both require a valid access token (query param `?token=` — browsers can't set
headers on a WebSocket). The connection is tied to that authenticated user.
A single MetricsHub / LogBus feeds every client; connecting does not spawn a
per-user collection loop.
"""
import uuid

import jwt
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import User, UserStatus
from app.services.logbus import bus
from app.services.monitor import hub

router = APIRouter(tags=["websocket"])

_POLICY_VIOLATION = status.WS_1008_POLICY_VIOLATION


def _authenticate(ws: WebSocket, db: Session) -> User | None:
    token = ws.query_params.get("token") or ""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None
    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        return None
    return user


@router.websocket("/ws/monitor")
async def ws_monitor(ws: WebSocket, db: Session = Depends(get_db)) -> None:
    user = _authenticate(ws, db)
    if user is None:
        await ws.close(code=_POLICY_VIOLATION)
        return
    username = user.username
    await ws.accept()
    await hub.start()
    q = hub.subscribe()
    await ws.send_json({"type": "hello", "channel": "monitor", "user": username})
    try:
        while True:
            await ws.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)


@router.websocket("/ws/logs")
async def ws_logs(ws: WebSocket, db: Session = Depends(get_db)) -> None:
    user = _authenticate(ws, db)
    if user is None:
        await ws.close(code=_POLICY_VIOLATION)
        return
    username = user.username
    await ws.accept()
    level = (ws.query_params.get("level") or "INFO").upper()
    q = bus.subscribe(min_level=level, backfill=50)
    await ws.send_json({"type": "hello", "channel": "logs", "user": username, "level": level})
    try:
        while True:
            await ws.send_json(await q.get())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(q)
