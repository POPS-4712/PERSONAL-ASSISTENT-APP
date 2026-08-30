"""In-process structured-log fan-out for the /ws/logs stream.

A logging.Handler captures every record, scrubs secrets, keeps a small ring
buffer for backfill, and pushes to any number of WebSocket subscriber queues.
Records can arrive from worker threads, so hand-off to the event loop is done
with call_soon_threadsafe.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from collections import deque

from app.core.logging import _SECRET_PATTERN

_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class LogBus(logging.Handler):
    def __init__(self, backlog: int = 200):
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._ring: deque[dict] = deque(maxlen=backlog)

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def detach_loop(self) -> None:
        self._loop = None

    # logging.Handler ---------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = self._to_event(record)
        except Exception:  # noqa: BLE001 - logging must never raise
            return
        loop = self._loop
        if loop is None or not loop.is_running():
            self._ring.append(event)
            return
        try:
            loop.call_soon_threadsafe(self._dispatch, event)
        except RuntimeError:
            self._ring.append(event)

    def _to_event(self, record: logging.LogRecord) -> dict:
        msg = _SECRET_PATTERN.sub(r"\1=***", record.getMessage())
        return {
            "type": "log",
            "timestamp": dt.datetime.fromtimestamp(record.created, dt.timezone.utc).isoformat(),
            "level": record.levelname,
            "source": record.name,
            "message": msg,
            "correlation_id": getattr(record, "correlation_id", None),
        }

    # loop thread -----------------------------------------------------------

    def _dispatch(self, event: dict) -> None:
        self._ring.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                self._subscribers.discard(q)

    # pub/sub -------------------------------------------------------------

    def subscribe(self, *, backfill: int = 50, min_level: str = "INFO") -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        threshold = _order(min_level)
        for event in list(self._ring)[-backfill:]:
            if _order(event["level"]) >= threshold:
                q.put_nowait(event)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)


def _order(level: str) -> int:
    return logging.getLevelName(level if level in _LEVELS else "INFO")


bus = LogBus()
