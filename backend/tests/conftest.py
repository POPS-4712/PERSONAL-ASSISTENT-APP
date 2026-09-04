from __future__ import annotations

import os

os.environ.setdefault("AC_ENVIRONMENT", "testing")
os.environ.setdefault("AC_DATABASE_URL", "sqlite+pysqlite:///:memory:")
# Keep the suite hermetic: a developer machine may export n8n / sidecar env
# (e.g. for the MCP tooling) that would otherwise leak into get_settings() and
# make the service-monitor tests non-deterministic. Integration tests that need
# a real n8n set these explicitly.
for _leak in (
    "N8N_API_KEY",
    "AC_N8N_API_KEY",
    "AC_N8N_BASE_URL",
    "N8N_API_URL",
    "N8N_URL",
    "AC_PLAYWRIGHT_BASE_URL",
    "AC_PROFILE_BASE_URL",
    "GEMINI_API_KEY",
    "AC_GEMINI_API_KEY",
):
    os.environ.pop(_leak, None)
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
def client(engine, session_factory, monkeypatch):
    app = create_app()

    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db

    # The service monitor opens its own sessions (it runs outside a request, in
    # the metrics-hub loop), so overriding get_db is not enough — point it at
    # the same in-memory database or every probe would read an empty schema.
    from app.services import services_probe

    monkeypatch.setattr(services_probe, "_session_factory", lambda: session_factory)
    services_probe.reset_gemini_cache()

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    services_probe.reset_gemini_cache()
