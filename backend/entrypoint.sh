#!/bin/sh
# Run pending migrations, then exec the given command (the API server).
# Idempotent: `alembic upgrade head` is a no-op when already current.
set -eu

if [ "${AC_RUN_MIGRATIONS:-1}" = "1" ]; then
  # ensure_database() connects to the "postgres" admin DB and CREATE DATABASEs
  # the target if missing. Managed providers (Render, Neon, Supabase, RDS)
  # pre-create the database and forbid that, so set AC_ENSURE_DATABASE=0 there.
  if [ "${AC_ENSURE_DATABASE:-1}" = "1" ]; then
    python -m app.bootstrap
  fi
  echo "{\"level\":\"INFO\",\"component\":\"entrypoint\",\"message\":\"alembic upgrade head\"}"
  alembic upgrade head
fi

exec "$@"
