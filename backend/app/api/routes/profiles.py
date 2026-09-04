
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.profile import (
    ProfileCatalogOut,
    ProfileCompletenessOut,
    ProfileCreate,
    ProfileDimensionsOut,
    ProfileDuplicate,
    ProfileOut,
    ProfileUpdate,
)
from app.services import profile_catalog
from app.services import profiles as svc

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _cid(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def _guard(fn):
    try:
        return fn()
    except svc.ProfileError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/dimensions", response_model=ProfileDimensionsOut)
def dimensions() -> ProfileDimensionsOut:
    return ProfileDimensionsOut(
        dimensions=list(svc.PROFILE_DIMENSIONS),
        note="configuration is an open JSON object; unknown keys are accepted",
    )


@router.get("/catalog", response_model=ProfileCatalogOut)
def catalog() -> ProfileCatalogOut:
    """The pickable options the personalisation UI renders.

    Public (no session): it is a static vocabulary, contains nothing about any
    user, and the login screen has no reason to hold it back.
    """
    return ProfileCatalogOut.model_validate(profile_catalog.as_dict())


@router.get("/completeness", response_model=ProfileCompletenessOut)
def completeness(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ProfileCompletenessOut:
    """Is the caller profile usable by the automations?

    Drives the setup wizard and the PROFILE tile on /monitoring. A profile row
    existing is not enough - the minimum fields must carry real values.
    """
    report = svc.completeness_for_user(db, user.id)
    return ProfileCompletenessOut(
        configured=report["configured"],
        profile_count=report["profile_count"],
        detail=report["detail"],
        required_fields=[label for label, _ in svc.REQUIRED_PROFILE_FIELDS],
        best=report["best"],
    )


@router.get("", response_model=list[ProfileOut])
def list_mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_profiles(db, user.id)


@router.post("", response_model=ProfileOut, status_code=201)
def create(
    request: Request,
    body: ProfileCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.create_profile(
            db,
            user.id,
            name=body.name,
            description=body.description,
            configuration=body.configuration,
            make_primary=body.make_primary,
            correlation_id=_cid(request),
        )
    )


@router.get("/{profile_id}", response_model=ProfileOut)
def get_one(
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(lambda: svc.get_profile(db, user.id, profile_id))


@router.patch("/{profile_id}", response_model=ProfileOut)
def update(
    request: Request,
    profile_id: uuid.UUID,
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.update_profile(
            db,
            user.id,
            profile_id,
            name=body.name,
            description=body.description,
            configuration=body.configuration,
            is_active=body.is_active,
            correlation_id=_cid(request),
        )
    )


@router.post("/{profile_id}/duplicate", response_model=ProfileOut, status_code=201)
def duplicate(
    request: Request,
    profile_id: uuid.UUID,
    body: ProfileDuplicate | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.duplicate_profile(
            db, user.id, profile_id, new_name=(body.name if body else None), correlation_id=_cid(request)
        )
    )


@router.delete("/{profile_id}", status_code=200)
def delete(
    request: Request,
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(lambda: svc.delete_profile(db, user.id, profile_id, correlation_id=_cid(request)))
    return {"deleted": True}


@router.post("/{profile_id}/activate", response_model=ProfileOut)
def activate(
    request: Request,
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.update_profile(
            db, user.id, profile_id, is_active=True, correlation_id=_cid(request)
        )
    )


@router.post("/{profile_id}/deactivate", response_model=ProfileOut)
def deactivate(
    request: Request,
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.update_profile(
            db, user.id, profile_id, is_active=False, correlation_id=_cid(request)
        )
    )


@router.post("/{profile_id}/primary", response_model=ProfileOut)
def make_primary(
    request: Request,
    profile_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(lambda: svc.set_primary(db, user.id, profile_id, correlation_id=_cid(request)))
