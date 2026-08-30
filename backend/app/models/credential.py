from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JsonB, TimestampMixin, uuid_pk


class CredentialType(str, enum.Enum):
    api_key = "api_key"
    bearer = "bearer"
    basic_auth = "basic_auth"
    oauth2 = "oauth2"
    custom = "custom"
    # kept for the enum value already present in provisioned databases
    service_token = "service_token"


class CredentialStatus(str, enum.Enum):
    connected = "connected"
    error = "error"
    untested = "untested"
    disabled = "disabled"


class Credential(Base, TimestampMixin):
    """A stored credential. The actual secret material lives ONLY in
    `encrypted_data` (Fernet, key held outside the DB). `hint` is the last few
    characters, safe to show. The plaintext is never returned by the API.
    """

    __tablename__ = "credentials"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_credential_user_name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # openai, google, telegram...
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[CredentialType] = mapped_column(
        Enum(CredentialType, name="credential_type"), nullable=False
    )
    status: Mapped[CredentialStatus] = mapped_column(
        Enum(CredentialStatus, name="credential_status"),
        default=CredentialStatus.untested,
        nullable=False,
    )
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    hint: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    meta: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_tested_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="credentials")  # noqa: F821
