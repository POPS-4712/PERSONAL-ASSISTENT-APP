from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonB, TimestampMixin, uuid_pk


class EventSeverity(str, enum.Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"
    critical = "critical"


class SystemEvent(Base, TimestampMixin):
    """Audit / diagnostics trail. Never store secrets in `message` or `meta`."""

    __tablename__ = "system_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity, name="event_severity"), default=EventSeverity.info, nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
