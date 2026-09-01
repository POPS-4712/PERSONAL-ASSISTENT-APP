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
Render  →  FastAPI web service (this repo's backend/Dockerfile)
             ▼
Render Postgres   ·   n8n / Playwright stay wherever they run (NOT on Vercel/Render serverless)
```

**Vercel cannot reach `localhost` / `127.0.0.1`.** The frontend runs in the
visitor's browser; `localhost` there is the visitor's own machine, not your
server. A cloud frontend therefore requires a backend published on a real
public HTTPS host.

**Status: the backend is prepared for Render but NOT yet deployed** — Render's
first deploy needs a human (GitHub connect + browser login), and the two
secret env vars must be pasted in the Render Dashboard. Once deployed the
public URL is `https://<service>.onrender.com`.

### Why Render

| Criterion | Fit |
|---|---|
| Docker | Builds `backend/Dockerfile` directly (`runtime: docker`). The image now binds `$PORT` (Render injects it); `${PORT:-8080}` keeps docker-compose unchanged. |
| FastAPI + uvicorn | Render **web service** = long-running process (not serverless). The metrics hub loop and n8n polling keep working. Use the **Starter** plan, not Free — Free instances sleep after 15 min idle. |
| WebSockets | `wss://` for `/ws/monitor` and `/ws/logs` works natively, no extra config. |
| HTTPS | Automatic on `*.onrender.com` (and custom domains). |
| Health checks | `healthCheckPath: /api/health` in the Blueprint. |
| PostgreSQL | Render Managed Postgres, wired via `fromDatabase` → `AC_DATABASE_URL`. The role cannot `CREATE DATABASE`, so `AC_ENSURE_DATABASE=0` skips `app/bootstrap.py`; `alembic upgrade head` still runs on every boot (idempotent). |
| Env vars / secrets | Blueprint `generateValue` / `sync: false` — secret values are set in the Dashboard, never in the repo or logs. |

The Blueprint lives at [`render.yaml`](../render.yaml) (repo root). `backend/fly.toml`
is kept only as a historical alternative and is not used.

### Backend deployment runbook (human steps — not run here)

Render deploys from a connected Git repo, and this repo currently has **no
remote**. Step 1 is therefore mandatory.

```sh
# 1. Publish the repo (GitHub example) — from the repo root:
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin master

# 2. Generate the credential-encryption key (needed in step 4). Copy the output:
python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"
```

3. **Render Dashboard → New → Blueprint** → pick the repo → **Apply**. Render
   reads `render.yaml` and creates `automation-center-db` + `automation-center-api`.
   `AC_JWT_SECRET` is auto-generated; `AC_DATABASE_URL` is wired automatically.

4. On the `automation-center-api` service → **Environment**, set the values
   flagged `sync: false` in `render.yaml`:

   | Key | Value |
   |---|---|
   | `AC_CREDENTIAL_ENCRYPTION_KEY` | the Fernet key from step 2 |
   | `AC_CORS_ORIGINS` | `https://tdrassistantproject.vercel.app` |
   | `AC_N8N_BASE_URL` | public HTTPS URL of a reachable n8n (see **n8n** below) — leave unset if none |
   | `AC_N8N_API_KEY` | the n8n API key — leave unset if none |

   Save → Render redeploys.

5. Verify (replace `<service>` with the real name Render shows):

```sh
curl -s https://<service>.onrender.com/api/health   # {"status":"ok"|"degraded", ...}
curl -s https://<service>.onrender.com/             # {"service":"automation-center-backend", ...}
```

Other managed Postgres (Neon, Supabase, RDS) instead of Render's: paste its
connection string as `AC_DATABASE_URL` (`postgres://…` is auto-normalised to the
`+psycopg` dialect) and keep `AC_ENSURE_DATABASE=0`.

## Frontend (Vercel) environment variables

Set in Vercel → Project → Settings → Environment Variables (never commit real
values). See `frontend/.env.example`.

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `https://<service>.onrender.com` | Public backend origin, **https**, no trailing slash, no path. Required. Set only once the Render URL exists. |
| `VITE_WS_URL`  | `wss://<service>.onrender.com` | WebSocket origin, **wss**. Optional — `src/config.ts` derives it from `VITE_API_URL` (`https→wss`) when unset, so you normally leave it blank. |
| `VITE_APP_ENV` | `production` | Cosmetic label only. |

If `VITE_API_URL` is unset the SPA falls back to `http://localhost:8080`, which
on an https Vercel page is broken (mixed content) and points nowhere useful.
**Always set it for any deployed environment.**

## Backend (public) environment variables

On top of the normal `AC_*` settings (`.env.example`):

| Variable | Value | Why |
|---|---|---|
| `AC_ENVIRONMENT` | `production` | Enforces real `AC_JWT_SECRET` + `AC_CREDENTIAL_ENCRYPTION_KEY` or the backend reports `degraded`. Set in `render.yaml`. |
| `AC_RUN_MIGRATIONS` | `1` (default) / `0` | `1`: entrypoint runs `alembic upgrade head` on boot (idempotent). |
| `AC_ENSURE_DATABASE` | `1` (default) / `0` | `1`: `app/bootstrap.py` `CREATE DATABASE`s the target if missing (needs an admin role). `0` on managed Postgres where the DB already exists and the role cannot create one. `render.yaml` sets `0`. |
| `AC_CORS_ORIGINS` | `https://tdrassistantproject.vercel.app` | Exact browser origin(s) of the frontend, comma-separated. The backend sends `Access-Control-Allow-Credentials: true`, so `*` is not allowed. |
| `AC_CORS_ORIGIN_REGEX` | `^https://<project>-[a-z0-9-]+\.vercel\.app$` | Optional, **only** to allow your own Vercel preview deployments. Never `.*`. |
| `AC_TRUSTED_PROXIES` | `10.0.0.0/8` on Render (its private range) | Without it `X-Forwarded-For` is ignored for rate-limiting (it is client-spoofable), so every request buckets by the proxy IP. |
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

## Vercel project status

The frontend is already deployed and live at
`https://tdrassistantproject.vercel.app` (HTTP 200, audited 2026-09-01).

### Wiring the frontend to the backend (human steps — dashboard)

Once `https://<service>.onrender.com/api/health` returns 200:

```
Vercel → Project (tdrassistantproject) → Settings → Environment Variables
  VITE_API_URL = https://<service>.onrender.com        (Production)
  (VITE_WS_URL is derived automatically — leave unset)
Then: Deployments → … → Redeploy   (env vars only apply to a new build)
```

Do **not** add any `AC_*`, `POSTGRES_*`, `N8N_*`, token, or `.env` value to
Vercel — the frontend needs none of them.

After that, on the Render service set
`AC_CORS_ORIGINS = https://tdrassistantproject.vercel.app` so the browser is
allowed to call the backend.
