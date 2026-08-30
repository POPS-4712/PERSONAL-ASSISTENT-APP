#!/bin/sh
# Run pending migrations, then exec the given command (the API server).
# Idempotent: `alembic upgrade head` is a no-op when already current.
set -eu

if [ "${AC_RUN_MIGRATIONS:-1}" = "1" ]; then
  python -m app.bootstrap
  echo "{\"level\":\"INFO\",\"component\":\"entrypoint\",\"message\":\"alembic upgrade head\"}"
  alembic upgrade head
fi

exec "$@"
