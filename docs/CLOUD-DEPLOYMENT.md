# Automation Center — Desktop vs Cloud

Two deployment shapes. They are mutually exclusive per browser session; the
frontend build is identical, only the `VITE_*` values differ.

## Desktop (supported today)

```
AutomationCenter-Setup.exe
  → Docker Desktop
      → postgres · n8n · playwright · profile · backend · frontend
Browser → http://localhost:3000  →  http://localhost:8080  (same machine)
```

The whole stack runs on the user's machine. Nothing is exposed to the internet.
This is what `installer/windows/*` installs and what v0.4.0 ships.

## Cloud

```
Vercel  →  static frontend (this repo's frontend/, Vite build)
             │  VITE_API_URL / VITE_WS_URL point at a PUBLIC backend
             ▼
Fly.io  →  FastAPI (this repo's backend/Dockerfile, unchanged)
             ▼
Fly Postgres   ·   n8n / Playwright stay wherever they run (NOT on Vercel/Fly serverless)
```

**Vercel cannot reach `localhost` / `127.0.0.1`.** The frontend runs in the
visitor's browser; `localhost` there is the visitor's own machine, not your
server. A cloud frontend therefore requires a backend published on a real
public HTTPS host.

**Status: the backend is prepared for Fly.io deployment but NOT yet deployed**
— no provider CLI is available in this environment and `fly` needs an
authenticated human. There is no public backend URL yet, so `VITE_API_URL`
cannot be set to a real value.

### Why Fly.io

| Criterion | Fit |
|---|---|
| Docker | Deploys `backend/Dockerfile` as-is. `internal_port = 8080` matches the image's `EXPOSE`/`CMD` — **no `$PORT` rewrite, no code change**. |
| FastAPI + uvicorn | Long-running process (not serverless) — the metrics hub background loop and n8n polling keep working. |
| WebSockets | `wss://` for `/ws/monitor` and `/ws/logs` works natively; `min_machines_running = 1` keeps the socket host warm. |
| HTTPS | Automatic on `*.fly.dev` (and custom domains). |
| Health checks | Native HTTP check against the real `/api/health`. |
| PostgreSQL | `fly postgres` — managed, same private network, superuser (so `app/bootstrap.py`'s `ensure_database()` works). |
| Env vars / secrets | `fly secrets set` — encrypted, never in the repo or logs. |
| Cost | Small `shared-cpu-1x` / 512 MB machine + a shared-cpu Postgres; fits the free/low tiers. |

Render and Railway also fit but both require the container to bind `$PORT`
(a Dockerfile change); Fly does not. The manifest lives at
[`backend/fly.toml`](../backend/fly.toml).

### Backend deployment runbook (human steps — not run here)

```sh
cd backend
fly launch --no-deploy --copy-config --name <your-app-name>   # keeps backend/fly.toml
fly postgres create --name <your-app-name>-db                 # managed Postgres
fly postgres attach <your-app-name>-db                        # sets DATABASE_URL secret
```

`fly postgres attach` creates a `DATABASE_URL` in the form
`postgres://user:pass@host:5432/db`. The backend needs the psycopg dialect, so
set it explicitly (do **not** rely on the auto-injected one):

```sh
fly secrets set \
  AC_DATABASE_URL='postgresql+psycopg://user:pass@<your-app-name>-db.flycast:5432/<db>' \
  AC_JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  AC_CREDENTIAL_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')"
# AC_CORS_ORIGINS is set AFTER the Vercel domain exists (see below):
#   fly secrets set AC_CORS_ORIGINS='https://<your-vercel-domain>'
# n8n integration (optional, only if n8n is also reachable from Fly):
#   fly secrets set AC_N8N_BASE_URL='https://<n8n-host>' AC_N8N_API_KEY='<key>'
fly deploy
```

Managed Postgres other than Fly's (Neon, Supabase, RDS): you usually cannot
`CREATE DATABASE`, so also set `AC_RUN_MIGRATIONS=0`, then run
`alembic upgrade head` once yourself against the provisioned database.

After `fly deploy`, the public URL is `https://<your-app-name>.fly.dev`.
Verify before wiring the frontend:

```sh
curl -s https://<your-app-name>.fly.dev/api/health        # {"status":"ok"|"degraded", ...}
curl -s https://<your-app-name>.fly.dev/                   # {"service":"automation-center-backend", ...}
```

## Frontend (Vercel) environment variables

Set in Vercel → Project → Settings → Environment Variables (never commit real
values). See `frontend/.env.example`.

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `https://<your-app-name>.fly.dev` | Public backend origin, **https**, no trailing slash, no path. Required. Set only once the Fly URL exists. |
| `VITE_WS_URL`  | `wss://<your-app-name>.fly.dev` | WebSocket origin, **wss**. Optional — `src/config.ts` derives it from `VITE_API_URL` (`https→wss`) when unset, so you normally leave it blank. |
| `VITE_APP_ENV` | `production` | Cosmetic label only. |

If `VITE_API_URL` is unset the SPA falls back to `http://localhost:8080`, which
on an https Vercel page is broken (mixed content) and points nowhere useful.
**Always set it for any deployed environment.**

## Backend (public) environment variables

On top of the normal `AC_*` settings (`.env.example`):

| Variable | Value | Why |
|---|---|---|
| `AC_ENVIRONMENT` | `production` | Enforces real `AC_JWT_SECRET` + `AC_CREDENTIAL_ENCRYPTION_KEY` or the backend reports `degraded`. Set in `backend/fly.toml` `[env]`. |
| `AC_RUN_MIGRATIONS` | `1` (default) / `0` | `1`: entrypoint runs `alembic upgrade head` on boot. Set `0` for managed Postgres where you must migrate manually. |
| `AC_CORS_ORIGINS` | `https://<your-vercel-domain>` | Exact browser origin(s) of the frontend, comma-separated. The backend sends `Access-Control-Allow-Credentials: true`, so `*` is not allowed. |
| `AC_CORS_ORIGIN_REGEX` | `https://<project>-[a-z0-9-]+\.vercel\.app` | Optional, **only** to allow your own Vercel preview deployments. Never `.*`. |
| `AC_TRUSTED_PROXIES` | egress CIDR of the load balancer / reverse proxy in front of the backend | Without it `X-Forwarded-For` is ignored for rate-limiting (it is client-spoofable). With a public backend behind a proxy you must set this or rate-limiting buckets by the proxy IP. |
| `AC_JWT_SECRET` | 32+ random chars | Session token signature. |
| `AC_CREDENTIAL_ENCRYPTION_KEY` | Fernet key (44 char base64url) | Credential store encryption at rest. |
| `AC_DATABASE_URL` | `postgresql+psycopg://…` | Automation Center's own DB. |
| `AC_N8N_BASE_URL` / `AC_N8N_API_KEY` | reachable n8n + API key | n8n integration. |

### Transport checklist for a public backend

- **HTTPS** terminated in front of uvicorn (uvicorn itself serves plain HTTP).
- **WSS**: the same TLS endpoint must proxy WebSocket upgrades to `/ws/monitor`
  and `/ws/logs` (`Upgrade` / `Connection` headers passed through).
- **JWT / refresh**: access token in the `Authorization: Bearer` header (SPA
  keeps it in memory); refresh token is sent in the JSON body of
  `POST /api/auth/refresh`. There are **no cookies** — CSRF is not a concern,
  but the frontend origin must be in `AC_CORS_ORIGINS`.
- WebSockets authenticate with `?token=<access>` (browsers cannot set headers on
  a WS). The socket is closed when that token expires or the user is revoked;
  the frontend refreshes and reconnects automatically on close code 1008.
- Security headers (`x-content-type-options`, `x-frame-options: DENY`,
  `referrer-policy: no-referrer`) are set by the backend middleware and by
  `frontend/vercel.json` for the static assets.

## Vercel project status (audited 2026-09-01, unchanged since 2026-08-31)

`vercel projects ls` under account `alexmogadesantiago-7031` shows one project:

| Project | Production URL | Notes |
|---|---|---|
| `moga_automatizaciones` | `https://mogaautomatizaciones.vercel.app` | **Not confirmed** to be the Automation Center frontend. |

No deploy was performed. Do not `vercel deploy`/link this repo to an existing
project without confirming it is the intended target — it would overwrite that
project.

### Vercel setup (human steps — dashboard, not run here)

```
Vercel → Add New… → Project → Import Git Repository → <this repo>
  Root Directory:    frontend
  Framework Preset:  Vite            (auto-detected; frontend/vercel.json confirms it)
  Build Command:     npm run build   (from vercel.json)
  Output Directory:  dist            (from vercel.json)
  Install Command:   npm install     (from vercel.json)
  Environment Variables:
      VITE_API_URL = https://<your-app-name>.fly.dev     ← only after the Fly backend is live
      (VITE_WS_URL and VITE_APP_ENV optional)
```

Do **not** add any `AC_*`, `POSTGRES_*`, `N8N_*`, token, or `.env` value to
Vercel — the frontend needs none of them.

After both are live: `fly secrets set AC_CORS_ORIGINS='https://<vercel-domain>'`
on the backend so the browser is allowed to call it.
