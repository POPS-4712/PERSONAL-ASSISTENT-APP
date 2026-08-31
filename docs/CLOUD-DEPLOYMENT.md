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

## Cloud (architecture only — NOT deployed in v0.4.0)

```
Vercel  →  static frontend (this repo's frontend/, Vite build)
             │  VITE_API_URL / VITE_WS_URL point at a PUBLIC backend
             ▼
Public backend (FastAPI, HTTPS)  →  Docker: postgres · n8n · playwright
```

**Vercel cannot reach `localhost` / `127.0.0.1`.** The frontend runs in the
visitor's browser; `localhost` there is the visitor's own machine, not your
server. A cloud frontend therefore requires a backend published on a real
public HTTPS host. There is no such host provisioned for this project yet, so
the cloud shape is documented but not live.

## Frontend (Vercel) environment variables

Set in Vercel → Project → Settings → Environment Variables (never commit real
values). See `frontend/.env.example`.

| Variable | Value | Notes |
|---|---|---|
| `VITE_API_URL` | `https://api.example.com` | Public backend origin, **https**, no trailing slash, no path. Required. |
| `VITE_WS_URL`  | `wss://api.example.com`  | WebSocket origin, **wss**. Optional — derived from `VITE_API_URL` (`https→wss`) if unset. |
| `VITE_APP_ENV` | `production` | Cosmetic label only. |

If `VITE_API_URL` is unset the SPA falls back to `http://localhost:8080`, which
on an https Vercel page is broken (mixed content) and points nowhere useful.
**Always set it for any deployed environment.**

## Backend (public) environment variables

On top of the normal `AC_*` settings (`.env.example`):

| Variable | Value | Why |
|---|---|---|
| `AC_ENVIRONMENT` | `production` | Enforces real `AC_JWT_SECRET` + `AC_CREDENTIAL_ENCRYPTION_KEY` or the backend reports `degraded`. |
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

## Vercel project status (as audited 2026-08-31)

`vercel projects ls` under account `alexmogadesantiago-7031` shows one project:

| Project | Production URL | Notes |
|---|---|---|
| `moga_automatizaciones` | `https://mogaautomatizaciones.vercel.app` | Updated recently; **not confirmed** to be the Automation Center frontend. |

No deploy was performed. Do not `vercel deploy`/link this repo to an existing
project without confirming it is the intended target — it would overwrite that
project. To deploy the Automation Center frontend, create a **dedicated**
Vercel project pointing at `frontend/` (root directory `frontend`, framework
Vite — `frontend/vercel.json` already carries the build + rewrite + header
config) and set the `VITE_*` variables above.
