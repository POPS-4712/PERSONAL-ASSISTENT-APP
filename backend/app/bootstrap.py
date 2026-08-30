"""One-shot startup helpers, safe to run every boot.

`ensure_database()` creates the Automation Center database if the Postgres
server doesn't have it yet (e.g. the volume was initialised before this feature
existed, so scripts/db-init/002 never ran). Idempotent.
"""
from __future__ import annotations

import sys
import time

import psycopg
from sqlalchemy.engine import make_url

from app.config import get_settings


def ensure_database(retries: int = 30, delay: float = 2.0) -> None:
    url = make_url(get_settings().database_url)
    target = url.database
    if not target or url.get_backend_name().startswith("sqlite"):
        return

    admin_dsn = (
        f"host={url.host or 'localhost'} port={url.port or 5432} "
        f"user={url.username} password={url.password} dbname=postgres"
    )

    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with psycopg.connect(admin_dsn, autocommit=True, connect_timeout=5) as conn:
                exists = conn.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (target,)
                ).fetchone()
                if not exists:
                    # identifier can't be parameterised; it comes from our own
                    # config, not user input.
                    conn.execute(f'CREATE DATABASE "{target}"')
                    print(f'{{"level":"INFO","component":"bootstrap","message":"created database {target}"}}')
                else:
                    print(f'{{"level":"INFO","component":"bootstrap","message":"database {target} present"}}')
            return
        except Exception as exc:  # noqa: BLE001 - retry loop for a slow Postgres
            last_err = exc
            print(
                f'{{"level":"WARN","component":"bootstrap","message":"postgres not ready '
                f'({attempt}/{retries}): {type(exc).__name__}"}}'
            )
            time.sleep(delay)
    raise SystemExit(f"could not reach Postgres to ensure database: {last_err}")


if __name__ == "__main__":
    ensure_database()
    sys.exit(0)
