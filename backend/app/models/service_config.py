from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonB, TimestampMixin


class ServiceConfig(Base, TimestampMixin):
    """Per-service configuration owned by the control plane, not by `.env`.

    One row per integration (`n8n`, `playwright`, `gemini`, ...). The row is the
    authoritative source when present; `app.services.service_config` falls back
    to the environment when it is absent, so an existing env-only deployment
    keeps working untouched.

    Secret material lives ONLY in `encrypted_secret` (Fernet, same master key as
    `credentials`). `secret_hint` is the last few characters and is the only
    part ever returned to a browser.
    """

    __tablename__ = "service_configs"

    # the service key is the identity — there is exactly one config per service
    service: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_url: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    encrypted_secret: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    secret_hint: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column(JsonB, default=dict, nullable=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_tested_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_detail: Mapped[str] = mapped_column(String(500), default="", nullable=False)
