from __future__ import annotations

import datetime as dt
import enum
import uuid

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    pending = "pending"


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.user, nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.active, nullable=False
    )
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profiles: Mapped[list["Profile"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    credentials: Mapped[list["Credential"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    workflows: Mapped[list["Workflow"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
