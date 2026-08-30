"""Append-only audit trail, written to `system_events`.

Never pass secrets in `message` or `meta`; the JSON log formatter scrubs common
key patterns as a backstop but callers own this.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models import EventSeverity, SystemEvent

log = logging.getLogger("audit")


def record(
    db: Session,
    *,
    type: str,
    message: str,
    severity: EventSeverity = EventSeverity.info,
    actor_id: uuid.UUID | str | None = None,
    correlation_id: str | None = None,
    meta: dict | None = None,
    commit: bool = True,
) -> SystemEvent:
    payload = dict(meta or {})
    if actor_id is not None:
        payload.setdefault("actor_id", str(actor_id))
    event = SystemEvent(
        type=type,
        severity=severity,
        message=message,
        meta=payload,
        correlation_id=correlation_id,
    )
    db.add(event)
    if commit:
        db.commit()
    log.info(message, extra={"operation": type, "correlation_id": correlation_id})
    return event
