from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonB, TimestampMixin, uuid_pk


class Profile(Base, TimestampMixin):
    """A user-defined profile. `configuration` is a validated JSON blob whose
    shape is driven by config/modules.json — deliberately schema-light so new
    dimensions can be added without a migration.
    """

    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_profile_user_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    configuration: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="profiles")  # noqa: F821
