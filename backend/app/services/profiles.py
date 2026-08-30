"""Profile CRUD. Every operation is scoped to one user; a caller can never see
or touch another user's rows (unknown ids look identical to other-user ids: 404).

`configuration` is an open JSON object. `PROFILE_DIMENSIONS` documents the
personalisation dimensions the product uses, but unknown keys are accepted so
new categories can be added without a schema change or migration.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import EventSeverity, Profile
from app.services import audit

PROFILE_DIMENSIONS: tuple[str, ...] = (
    "formacion",
    "sector",
    "objetivo_profesional",
    "ubicacion",
    "modalidad",
    "experiencia_nivel",
    "intereses",
    "preferencias_laborales",
    "preferencias_noticias",
    "marca_personal",
    "automatizaciones",
)


class ProfileError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFound(ProfileError):
    def __init__(self) -> None:
        super().__init__("profile not found", 404)


def _get_owned(db: Session, user_id: uuid.UUID, profile_id: uuid.UUID) -> Profile:
    row = db.scalar(
        select(Profile).where(Profile.id == profile_id, Profile.user_id == user_id)
    )
    if row is None:
        raise NotFound()
    return row


def list_profiles(db: Session, user_id: uuid.UUID) -> list[Profile]:
    return list(
        db.scalars(
            select(Profile)
            .where(Profile.user_id == user_id)
            .order_by(Profile.is_primary.desc(), Profile.created_at.asc())
        )
    )


def get_profile(db: Session, user_id: uuid.UUID, profile_id: uuid.UUID) -> Profile:
    return _get_owned(db, user_id, profile_id)


def create_profile(
    db: Session,
    user_id: uuid.UUID,
    *,
    name: str,
    description: str = "",
    configuration: dict | None = None,
    make_primary: bool = False,
    correlation_id: str | None = None,
) -> Profile:
    name = name.strip()
    if not name:
        raise ProfileError("name is required")
    dup = db.scalar(
        select(Profile).where(Profile.user_id == user_id, func.lower(Profile.name) == name.lower())
    )
    if dup is not None:
        raise ProfileError("a profile with that name already exists", 409)

    first = db.scalar(select(func.count()).select_from(Profile).where(Profile.user_id == user_id)) == 0
    profile = Profile(
        user_id=user_id,
        name=name,
        description=(description or "").strip(),
        configuration=configuration or {},
        is_active=True,
        is_primary=bool(make_primary or first),
    )
    db.add(profile)
    db.flush()
    if profile.is_primary:
        _clear_other_primary(db, user_id, keep=profile.id)
    audit.record(
        db,
        type="profile.create",
        message=f"profile created: {name}",
        actor_id=user_id,
        correlation_id=correlation_id,
        commit=False,
    )
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(
    db: Session,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    configuration: dict | None = None,
    is_active: bool | None = None,
    correlation_id: str | None = None,
) -> Profile:
    profile = _get_owned(db, user_id, profile_id)
    if name is not None:
        name = name.strip()
        if not name:
            raise ProfileError("name cannot be empty")
        clash = db.scalar(
            select(Profile).where(
                Profile.user_id == user_id,
                func.lower(Profile.name) == name.lower(),
                Profile.id != profile_id,
            )
        )
        if clash is not None:
            raise ProfileError("a profile with that name already exists", 409)
        profile.name = name
    if description is not None:
        profile.description = description.strip()
    if configuration is not None:
        profile.configuration = configuration
    if is_active is not None:
        if not is_active and profile.is_primary:
            raise ProfileError("cannot deactivate the primary profile", 409)
        profile.is_active = is_active
    audit.record(
        db,
        type="profile.update",
        message=f"profile updated: {profile.name}",
        actor_id=user_id,
        correlation_id=correlation_id,
        commit=False,
    )
    db.commit()
    db.refresh(profile)
    return profile


def duplicate_profile(
    db: Session,
    user_id: uuid.UUID,
    profile_id: uuid.UUID,
    *,
    new_name: str | None = None,
    correlation_id: str | None = None,
) -> Profile:
    src = _get_owned(db, user_id, profile_id)
    name = (new_name or f"{src.name} (copia)").strip()
    n = 2
    while db.scalar(
        select(Profile).where(Profile.user_id == user_id, func.lower(Profile.name) == name.lower())
    ) is not None:
        name = f"{src.name} (copia {n})"
        n += 1
    clone = Profile(
        user_id=user_id,
        name=name,
        description=src.description,
        configuration=dict(src.configuration or {}),
        is_active=True,
        is_primary=False,
    )
    db.add(clone)
    audit.record(
        db,
        type="profile.duplicate",
        message=f"profile duplicated from {src.name} -> {name}",
        actor_id=user_id,
        correlation_id=correlation_id,
        commit=False,
    )
    db.commit()
    db.refresh(clone)
    return clone


def delete_profile(
    db: Session, user_id: uuid.UUID, profile_id: uuid.UUID, *, correlation_id: str | None = None
) -> None:
    profile = _get_owned(db, user_id, profile_id)
    was_primary = profile.is_primary
    db.delete(profile)
    db.flush()
    if was_primary:
        # promote the oldest remaining profile so the user always has a primary
        nxt = db.scalar(
            select(Profile)
            .where(Profile.user_id == user_id)
            .order_by(Profile.created_at.asc())
        )
        if nxt is not None:
            nxt.is_primary = True
    audit.record(
        db,
        type="profile.delete",
        message=f"profile deleted: {profile.name}",
        severity=EventSeverity.warning,
        actor_id=user_id,
        correlation_id=correlation_id,
        commit=False,
    )
    db.commit()


def set_primary(
    db: Session, user_id: uuid.UUID, profile_id: uuid.UUID, *, correlation_id: str | None = None
) -> Profile:
    profile = _get_owned(db, user_id, profile_id)
    if not profile.is_active:
        raise ProfileError("activate the profile before making it primary", 409)
    _clear_other_primary(db, user_id, keep=profile.id)
    profile.is_primary = True
    audit.record(
        db,
        type="profile.set_primary",
        message=f"primary profile set: {profile.name}",
        actor_id=user_id,
        correlation_id=correlation_id,
        commit=False,
    )
    db.commit()
    db.refresh(profile)
    return profile


def _clear_other_primary(db: Session, user_id: uuid.UUID, *, keep: uuid.UUID) -> None:
    for row in db.scalars(
        select(Profile).where(
            Profile.user_id == user_id, Profile.is_primary.is_(True), Profile.id != keep
        )
    ):
        row.is_primary = False
    db.flush()
