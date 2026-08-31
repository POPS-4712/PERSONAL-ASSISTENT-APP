"""WebSocket endpoints: /ws/monitor and /ws/logs.

Both require a valid access token (query param `?token=` — browsers can't set
headers on a WebSocket). The connection is tied to that authenticated user.
A single MetricsHub / LogBus feeds every client; connecting does not spawn a
per-user collection loop.

Auth is enforced for the *lifetime* of the socket, not just at connect:

* the connection is closed when the access token's own ``exp`` passes, so a
  long-lived stream cannot outlive the token that opened it;
* the user's status is re-checked periodically, so a disabled/deleted user is
  dropped within ``_STATUS_RECHECK_SECONDS`` without waiting for token expiry.

Both closes use code 1008; the frontend reacts to 1008 by refreshing its access
token and reconnecting, so automatic reconnection keeps working.
"""
import asyncio
import time
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
_STATUS_RECHECK_SECONDS = 30.0


def _authenticate(ws: WebSocket, db: Session) -> tuple[User, int] | None:
    """Return (user, token_exp_epoch) or None."""
    token = ws.query_params.get("token") or ""
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        token_exp = int(payload["exp"])
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        return None
    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        return None
    return user, token_exp


async def _pump(ws: WebSocket, queue: asyncio.Queue, *, token_exp: int, db: Session, user_id: uuid.UUID) -> None:
    """Forward queue items to the socket until disconnect, token expiry, or the
    user being revoked."""
    next_check = time.time() + _STATUS_RECHECK_SECONDS
    while True:
        now = time.time()
        if now >= token_exp:
            await ws.close(code=_POLICY_VIOLATION)
            return
        if now >= next_check:
            db.expire_all()
            user = db.get(User, user_id)
            if user is None or user.status != UserStatus.active:
                await ws.close(code=_POLICY_VIOLATION)
                return
            next_check = now + _STATUS_RECHECK_SECONDS
        wait = max(0.1, min(token_exp - now, next_check - now))
        try:
            item = await asyncio.wait_for(queue.get(), timeout=wait)
        except asyncio.TimeoutError:
            continue
        await ws.send_json(item)


@router.websocket("/ws/monitor")
async def ws_monitor(ws: WebSocket, db: Session = Depends(get_db)) -> None:
    auth = _authenticate(ws, db)
    if auth is None:
        await ws.close(code=_POLICY_VIOLATION)
        return
    user, token_exp = auth
    await ws.accept()
    await hub.start()
    q = hub.subscribe()
    await ws.send_json({"type": "hello", "channel": "monitor", "user": user.username})
    try:
        await _pump(ws, q, token_exp=token_exp, db=db, user_id=user.id)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.unsubscribe(q)


@router.websocket("/ws/logs")
async def ws_logs(ws: WebSocket, db: Session = Depends(get_db)) -> None:
    auth = _authenticate(ws, db)
    if auth is None:
        await ws.close(code=_POLICY_VIOLATION)
        return
    user, token_exp = auth
    await ws.accept()
    level = (ws.query_params.get("level") or "INFO").upper()
    q = bus.subscribe(min_level=level, backfill=50)
    await ws.send_json({"type": "hello", "channel": "logs", "user": user.username, "level": level})
    try:
        await _pump(ws, q, token_exp=token_exp, db=db, user_id=user.id)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(q)
