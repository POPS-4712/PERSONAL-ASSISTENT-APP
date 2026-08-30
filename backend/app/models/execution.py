from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class ExecutionStatus(str, enum.Enum):
    success = "success"
    running = "running"
    failed = "failed"
    waiting = "waiting"
    cancelled = "cancelled"


class Execution(Base, TimestampMixin):
    __tablename__ = "executions"
    __table_args__ = (
        UniqueConstraint("workflow_id", "external_execution_id", name="uq_execution_ext"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True, nullable=False
    )
    external_execution_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status"), default=ExecutionStatus.running, nullable=False
    )
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow: Mapped["Workflow"] = relationship(back_populates="executions")  # noqa: F821
