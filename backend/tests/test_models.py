from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Credential,
    CredentialType,
    Execution,
    ExecutionStatus,
    Profile,
    SystemEvent,
    User,
    UserRole,
    Workflow,
)


def _user(**kw) -> User:
    base = dict(
        email=f"{uuid.uuid4().hex}@example.com",
        username=uuid.uuid4().hex[:12],
        password_hash="x",
    )
    base.update(kw)
    return User(**base)


def test_user_defaults(db_session):
    u = _user()
    db_session.add(u)
    db_session.commit()
    assert u.role == UserRole.user
    assert u.status.value == "active"
    assert u.created_at is not None


def test_unique_email(db_session):
    email = f"{uuid.uuid4().hex}@example.com"
    db_session.add(_user(email=email))
    db_session.commit()
    db_session.add(_user(email=email))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_cascade_delete(db_session):
    u = _user()
    db_session.add(u)
    db_session.flush()
    p = Profile(user_id=u.id, name="Ingeniería", configuration={"idioma": ["es"]})
    c = Credential(
        user_id=u.id,
        provider="openai",
        name="OpenAI",
        type=CredentialType.api_key,
        encrypted_data=b"ciphertext",
        hint="8F3A",
    )
    w = Workflow(user_id=u.id, name="News", n8n_workflow_id="abc123")
    db_session.add_all([p, c, w])
    db_session.flush()
    db_session.add(Execution(workflow_id=w.id, status=ExecutionStatus.success))
    db_session.commit()

    db_session.delete(u)
    db_session.commit()
    assert db_session.query(Profile).count() == 0
    assert db_session.query(Credential).count() == 0
    assert db_session.query(Workflow).count() == 0
    assert db_session.query(Execution).count() == 0


def test_system_event(db_session):
    ev = SystemEvent(type="install.step", message="detecting", meta={"step": "detecting"})
    db_session.add(ev)
    db_session.commit()
    assert ev.severity.value == "info"
