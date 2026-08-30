from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonB, TimestampMixin, uuid_pk


class WorkflowStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    unknown = "unknown"


class Workflow(Base, TimestampMixin):
    """Automation Center's view of an n8n workflow. `n8n_workflow_id` links it to
    the live workflow in the n8n instance; the rest is our metadata/manifest.
    """

    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("user_id", "n8n_workflow_id", name="uq_workflow_user_n8nid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="", nullable=False)
    slug: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    n8n_workflow_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status"), default=WorkflowStatus.unknown, nullable=False
    )
    meta: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="workflows")  # noqa: F821
    executions: Mapped[list["Execution"]] = relationship(  # noqa: F821
        back_populates="workflow", cascade="all, delete-orphan"
    )
