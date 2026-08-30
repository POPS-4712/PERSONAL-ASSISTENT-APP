from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class RefreshToken(Base, TimestampMixin):
    """One row per issued refresh token. The raw token is never stored, only its
    SHA-256. Rotation: on use, the row is marked revoked and `replaced_by` points
    at the successor. Re-use of a revoked token revokes the whole family.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    user_agent: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    client_ip: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    user: Mapped["User"] = relationship()  # noqa: F821

    @property
    def is_active(self) -> bool:
        now = dt.datetime.now(dt.timezone.utc)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=dt.timezone.utc)
        return self.revoked_at is None and exp > now
