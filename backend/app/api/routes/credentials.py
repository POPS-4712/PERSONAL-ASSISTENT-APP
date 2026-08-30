import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core import crypto
from app.db import get_db
from app.models import CredentialType, User
from app.schemas.credential import (
    CredentialCreate,
    CredentialOut,
    CredentialTestOut,
    CredentialUpdate,
)
from app.services import credentials as svc

router = APIRouter(prefix="/credentials", tags=["credentials"])


def _cid(request: Request):
    return getattr(request.state, "correlation_id", None)


def _guard(fn):
    try:
        return fn()
    except svc.CredentialError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("", response_model=list[CredentialOut])
def list_mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.list_credentials(db, user.id)


@router.get("/store-status")
def store_status():
    """Whether the encryption master key is configured (no secret is exposed)."""
    return {"configured": crypto.is_configured()}


@router.post("", response_model=CredentialOut, status_code=201)
def create(
    request: Request,
    body: CredentialCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.create_credential(
            db,
            user.id,
            provider=body.provider,
            name=body.name,
            type=CredentialType(body.type),
            secret=body.secret,
            meta=body.meta,
            correlation_id=_cid(request),
        )
    )


@router.get("/{credential_id}", response_model=CredentialOut)
def get_one(
    credential_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(lambda: svc.get_credential(db, user.id, credential_id))


@router.patch("/{credential_id}", response_model=CredentialOut)
def update(
    request: Request,
    credential_id: uuid.UUID,
    body: CredentialUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _guard(
        lambda: svc.update_credential(
            db,
            user.id,
            credential_id,
            name=body.name,
            secret=body.secret,
            meta=body.meta,
            is_enabled=body.is_enabled,
            correlation_id=_cid(request),
        )
    )


@router.delete("/{credential_id}", status_code=200)
def delete(
    request: Request,
    credential_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _guard(lambda: svc.delete_credential(db, user.id, credential_id, correlation_id=_cid(request)))
    return {"deleted": True}


@router.post("/{credential_id}/test", response_model=CredentialTestOut)
async def test(
    request: Request,
    credential_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return await svc.test_connection(db, user.id, credential_id, correlation_id=_cid(request))
    except svc.CredentialError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
