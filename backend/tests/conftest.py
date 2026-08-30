from __future__ import annotations

import os

os.environ.setdefault("AC_ENVIRONMENT", "testing")
os.environ.setdefault("AC_DATABASE_URL", "sqlite+pysqlite:///:memory:")
# A real Fernet key so the credential-manager tests exercise real encryption.
os.environ.setdefault(
    "AC_CREDENTIAL_ENCRYPTION_KEY", "jpVUkdjPW0gHZ-5-bSUieGJIkYo3Mjdn-8rCdSV7Qro="
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import create_app
from app.models import Base


@pytest.fixture
def engine():
    """A fresh in-memory database per test — isolation matters for the auth and
    multi-user tests (e.g. "first registered user is admin").
    """
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(engine, session_factory):
    app = create_app()

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
