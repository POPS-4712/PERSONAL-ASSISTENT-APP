# Automation Center — backend

FastAPI + SQLAlchemy 2 + Alembic + Postgres. Runs as the `backend` service in
`docker-compose.yml` (`pa-backend`, `127.0.0.1:8080`).

## Layout

```
app/
  config.py          settings (env prefix AC_), validate_runtime()
  db.py              engine + session (sync, psycopg 3)
  main.py            FastAPI app factory, CORS, security headers, request id
  core/logging.py    structured JSON logs, secret scrubbing
  models/            SQLAlchemy models (users, profiles, credentials,
                     workflows, executions, system_events)
  schemas/           pydantic response models
  services/
    metrics.py         real host/container metrics (psutil)
    services_probe.py   live TCP/HTTP probes of every stack service
  api/routes/        routers; mounted under /api
migrations/          Alembic (0001_initial creates the whole schema)
tests/               pytest (SQLite in-memory; `-m integration` needs real PG)
```

## Endpoints (phase 3)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | backend liveness + DB check + `validate_runtime()` problems |
| GET | `/api/system/status` | live probe of postgres / n8n / playwright / profile |
| GET | `/api/system/metrics` | real CPU / RAM / disk / load / uptime |
| GET | `/openapi.json`, `/docs` | OpenAPI schema + Swagger UI |

Auth, profiles, credentials, n8n integration and WebSockets land in phases 4–8.

## Dev

```bash
# tests (no services needed)
docker build --target test -t pa-backend-test ./backend

# run against the stack
docker compose up -d postgres backend
curl -s localhost:8080/api/health | jq

# migrations
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade base
```

Local venv needs Python 3.11–3.13 (pydantic-core has no 3.14 wheel yet); the
container uses 3.12.
