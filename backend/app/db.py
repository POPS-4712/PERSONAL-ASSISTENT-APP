"""SQLAlchemy engine and session wiring (synchronous, psycopg 3).

FastAPI runs sync dependencies in a threadpool, which is plenty for this
workload (the hot path is Docker/n8n polling, not the DB). Keeping it sync makes
Alembic and the test suite trivial.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_settings = get_settings()

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "echo": _settings.debug and _settings.environment == "development",
}
# Connection-pool sizing only applies to a real server pool (Postgres); SQLite
# (used by the test suite) rejects those arguments.
if not _settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(pool_size=5, max_overflow=10)

engine = create_engine(_settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: yields a session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
