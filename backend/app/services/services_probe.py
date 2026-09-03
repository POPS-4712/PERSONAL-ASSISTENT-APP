"""Liveness of the stack's services.

Every check is real: the database check reuses the application's own engine
(the connection the app actually depends on), and the HTTP services are probed
with a real GET. Nothing here returns a hard-coded "ONLINE".

Four states are reported per service:

* ``online``          - configured for this environment and responding.
* ``offline``         - configured but not responding.
* ``not_configured``  - no endpoint configured for this environment (e.g. n8n
                        on a single-service Render deploy). Not an error.
* ``unknown``         - the probe itself could not run.

Docker Compose sets ``AC_PLAYWRIGHT_BASE_URL`` / ``AC_PROFILE_BASE_URL`` (and
usually ``AC_N8N_API_KEY``) so the full local stack shows every service. A
stand-alone deploy that only runs the backend leaves them unset and those
services report ``not_configured`` instead of a misleading ``offline``.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import time
from dataclasses import dataclass

import httpx
from sqlalchemy import text

from app.config import get_settings

ONLINE = "online"
OFFLINE = "offline"
NOT_CONFIGURED = "not_configured"
UNKNOWN = "unknown"

# Services whose failure means the platform itself is not operational. n8n /
# playwright / profile are optional integrations — their absence must not make
# the whole system look broken.
CRITICAL_SERVICES = frozenset({"postgres"})


@dataclass
class ServiceState:
    name: str
    kind: str  # db | http
    target: str  # host:port or URL — never contains a secret
    status: str  # online | offline | not_configured | unknown
    online: bool | None  # derived from status; kept for API/back-compat
    detail: str
    latency_ms: float | None


def _state(name: str, kind: str, target: str, status: str, detail: str, latency: float | None) -> ServiceState:
    online = True if status == ONLINE else False if status == OFFLINE else None
    return ServiceState(name, kind, target, status, online, detail, latency)


async def _probe_http(url: str, timeout: float = 3.0) -> tuple[bool, float | None, str]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
        return (
            200 <= r.status_code < 400,
            round(r.elapsed.total_seconds() * 1000, 1),
            f"HTTP {r.status_code}",
        )
    except httpx.HTTPError as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


def _check_database_sync() -> tuple[bool, float | None, str]:
    """Use the application's own engine — the connection the app really uses."""
    from app.db import engine

    start = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, round((time.perf_counter() - start) * 1000, 1), "SELECT 1 ok"
    except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
        return False, None, f"{type(exc).__name__}: {exc}"


async def _check_database() -> ServiceState:
    ok, lat, detail = await asyncio.to_thread(_check_database_sync)
    return _state("postgres", "db", "application database", ONLINE if ok else OFFLINE, detail, lat)


async def _check_http_service(name: str, base_url: str, health_path: str) -> ServiceState:
    base = base_url.rstrip("/")
    url = f"{base}{health_path}"
    ok, lat, detail = await _probe_http(url)
    return _state(name, "http", url, ONLINE if ok else OFFLINE, detail, lat)


async def _check_n8n() -> ServiceState:
    s = get_settings()
    # The n8n integration is "configured" once an API key exists — a bare
    # /healthz being reachable does not make the integration usable, and this
    # mirrors the N8nNotConfigured gate in services/n8n.py.
    if not s.n8n_api_key:
        return _state("n8n", "http", "", NOT_CONFIGURED, "AC_N8N_API_KEY not set", None)
    if not s.n8n_base_url:
        return _state("n8n", "http", "", NOT_CONFIGURED, "AC_N8N_BASE_URL not set", None)
    return await _check_http_service("n8n", s.n8n_base_url, "/healthz")


async def _check_optional_http(name: str, base_url: str, env_name: str, health_path: str) -> ServiceState:
    if not base_url:
        return _state(name, "http", "", NOT_CONFIGURED, f"{env_name} not set", None)
    return await _check_http_service(name, base_url, health_path)


async def probe_services() -> list[ServiceState]:
    s = get_settings()
    results = await asyncio.gather(
        _check_database(),
        _check_n8n(),
        _check_optional_http("playwright", s.playwright_base_url, "AC_PLAYWRIGHT_BASE_URL", "/health"),
        _check_optional_http("profile", s.profile_base_url, "AC_PROFILE_BASE_URL", "/health"),
        return_exceptions=True,
    )
    names = ("postgres", "n8n", "playwright", "profile")
    out: list[ServiceState] = []
    for name, r in zip(names, results):
        if isinstance(r, ServiceState):
            out.append(r)
        else:  # a probe raised — surface it as unknown, don't crash the endpoint
            out.append(_state(name, "http", "", UNKNOWN, f"probe error: {type(r).__name__}", None))
    return out


async def system_status() -> dict:
    services = await probe_services()

    critical_ok = all(
        s.status == ONLINE for s in services if s.name in CRITICAL_SERVICES
    )
    any_configured_offline = any(s.status == OFFLINE for s in services)
    operational = critical_ok and not any_configured_offline

    return {
        "operational": operational,
        "state": "operational" if operational else "degraded",
        "degraded_services": [s.name for s in services if s.status == OFFLINE],
        "not_configured_services": [s.name for s in services if s.status == NOT_CONFIGURED],
        "services": [s.__dict__ for s in services],
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
