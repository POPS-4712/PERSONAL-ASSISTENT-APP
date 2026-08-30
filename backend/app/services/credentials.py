"""Credential manager: encrypted-at-rest secrets, user-scoped, audited.

Guarantees enforced here and covered by tests:
- the plaintext secret is never returned by any read path;
- `encrypted_data` never leaves this module;
- another user's credential is a 404, not a 403;
- without the master key, stored secrets cannot be decrypted;
- every create/update/delete/decrypt/test is written to the audit trail.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import crypto
from app.models import Credential, CredentialStatus, CredentialType, EventSeverity
from app.services import audit
from app.services.credential_test import run_test


class CredentialError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFound(CredentialError):
    def __init__(self) -> None:
        super().__init__("credential not found", 404)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _hint_for(secret: dict) -> str:
    material = secret.get("api_key") or secret.get("token") or secret.get("access_token") or secret.get("value") or ""
    material = str(material)
    if len(material) <= 4:
        return "*" * len(material)
    return "…" + material[-4:]


def _owned(db: Session, user_id: uuid.UUID, credential_id: uuid.UUID) -> Credential:
    row = db.scalar(
        select(Credential).where(Credential.id == credential_id, Credential.user_id == user_id)
    )
    if row is None:
        raise NotFound()
    return row


def list_credentials(db: Session, user_id: uuid.UUID) -> list[Credential]:
    return list(
        db.scalars(
            select(Credential)
            .where(Credential.user_id == user_id)
            .order_by(Credential.provider, Credential.name)
        )
    )


def get_credential(db: Session, user_id: uuid.UUID, credential_id: uuid.UUID) -> Credential:
    return _owned(db, user_id, credential_id)


def create_credential(
    db: Session,
    user_id: uuid.UUID,
    *,
    provider: str,
    name: str,
    type: CredentialType,
    secret: dict,
    meta: dict | None = None,
    correlation_id: str | None = None,
) -> Credential:
    if not crypto.is_configured():
        raise CredentialError("credential store is not configured (AC_CREDENTIAL_ENCRYPTION_KEY)", 503)
    provider = provider.strip().lower()
    name = name.strip()
    if not provider or not name:
        raise CredentialError("provider and name are required")
    if not isinstance(secret, dict) or not any(str(v).strip() for v in secret.values()):
        raise CredentialError("secret must be a non-empty object")
    clash = db.scalar(
        select(Credential).where(
            Credential.user_id == user_id, func.lower(Credential.name) == name.lower()
        )
    )
    if clash is not None:
        raise CredentialError("a credential with that name already exists", 409)

    row = Credential(
        user_id=user_id,
        provider=provider,
        name=name,
        type=type,
        status=CredentialStatus.untested,
        encrypted_data=crypto.encrypt_secret(secret),
        hint=_hint_for(secret),
        meta=_sanitise_meta(meta or {}),
    )
    db.add(row)
    db.flush()
    audit.record(
        db,
        type="credential.create",
        message=f"credential created: {provider}/{name}",
        actor_id=user_id,
        correlation_id=correlation_id,
        meta={"provider": provider, "type": type.value, "credential_id": str(row.id)},
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


def update_credential(
    db: Session,
    user_id: uuid.UUID,
    credential_id: uuid.UUID,
    *,
    name: str | None = None,
    secret: dict | None = None,
    meta: dict | None = None,
    is_enabled: bool | None = None,
    correlation_id: str | None = None,
) -> Credential:
    row = _owned(db, user_id, credential_id)
    if name is not None:
        name = name.strip()
        if not name:
            raise CredentialError("name cannot be empty")
        row.name = name
    if secret is not None:
        if not crypto.is_configured():
            raise CredentialError("credential store is not configured", 503)
        if not isinstance(secret, dict) or not any(str(v).strip() for v in secret.values()):
            raise CredentialError("secret must be a non-empty object")
        row.encrypted_data = crypto.encrypt_secret(secret)
        row.hint = _hint_for(secret)
        row.status = CredentialStatus.untested
    if meta is not None:
        row.meta = _sanitise_meta(meta)
    if is_enabled is not None:
        row.is_enabled = is_enabled
        if not is_enabled:
            row.status = CredentialStatus.disabled
    audit.record(
        db,
        type="credential.update",
        message=f"credential updated: {row.provider}/{row.name}",
        actor_id=user_id,
        correlation_id=correlation_id,
        meta={"credential_id": str(row.id), "secret_rotated": secret is not None},
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return row


def delete_credential(
    db: Session, user_id: uuid.UUID, credential_id: uuid.UUID, *, correlation_id: str | None = None
) -> None:
    row = _owned(db, user_id, credential_id)
    provider, name, cid = row.provider, row.name, str(row.id)
    db.delete(row)
    audit.record(
        db,
        type="credential.delete",
        message=f"credential deleted: {provider}/{name}",
        severity=EventSeverity.warning,
        actor_id=user_id,
        correlation_id=correlation_id,
        meta={"credential_id": cid},
        commit=False,
    )
    db.commit()


def reveal_secret(
    db: Session,
    user_id: uuid.UUID,
    credential_id: uuid.UUID,
    *,
    requested_by: str,
    correlation_id: str | None = None,
) -> dict:
    """Internal only. Decrypts a credential for an authorised server-side
    consumer (e.g. a workflow runner). NOT exposed through any API route.
    Every call is audited.
    """
    row = _owned(db, user_id, credential_id)
    if not row.is_enabled:
        raise CredentialError("credential is disabled", 409)
    secret = crypto.decrypt_secret(row.encrypted_data)  # raises DecryptionError w/o key
    row.last_used_at = _now()
    audit.record(
        db,
        type="credential.reveal",
        message=f"credential secret accessed by {requested_by}: {row.provider}/{row.name}",
        severity=EventSeverity.warning,
        actor_id=user_id,
        correlation_id=correlation_id,
        meta={"credential_id": str(row.id), "requested_by": requested_by},
    )
    return secret


async def test_connection(
    db: Session, user_id: uuid.UUID, credential_id: uuid.UUID, *, correlation_id: str | None = None
) -> dict:
    row = _owned(db, user_id, credential_id)
    secret = crypto.decrypt_secret(row.encrypted_data)
    result = await run_test(row.provider, row.type, secret, row.meta or {})

    row.status = CredentialStatus.connected if result.ok else CredentialStatus.error
    row.last_tested_at = _now()
    audit.record(
        db,
        type="credential.test",
        message=f"credential test {row.provider}/{row.name}: {'ok' if result.ok else 'failed'}",
        severity=EventSeverity.info if result.ok else EventSeverity.warning,
        actor_id=user_id,
        correlation_id=correlation_id,
        meta={"credential_id": str(row.id), "detail": result.detail},
    )
    return {"ok": result.ok, "detail": result.detail, "latency_ms": result.latency_ms, "status": row.status.value}


def _sanitise_meta(meta: dict) -> dict:
    """meta is public (returned by the API). Drop anything that smells secret."""
    banned = ("password", "secret", "token", "api_key", "apikey", "key", "authorization")
    return {k: v for k, v in meta.items() if k.lower() not in banned}
