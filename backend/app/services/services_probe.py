"""Liveness of the stack's services.

Every check is a real network probe (TCP connect, and an HTTP GET where the
service has a health endpoint). Nothing here returns a hard-coded "ONLINE".
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import get_settings


@dataclass
class ServiceState:
    name: str
    kind: str  # tcp | http
    target: str
    online: bool
    detail: str
    latency_ms: float | None


# name -> (host, port, optional health URL)
def _targets() -> list[tuple[str, str, int, str | None]]:
    s = get_settings()
    n8n = urlparse(s.n8n_base_url)
    n8n_host = n8n.hostname or "n8n"
    n8n_port = n8n.port or 5678
    return [
        ("postgres", "postgres", 5432, None),
        ("n8n", n8n_host, n8n_port, f"{s.n8n_base_url.rstrip('/')}/healthz"),
        ("playwright", "playwright", 3000, "http://playwright:3000/health"),
        ("profile", "profile", 7777, "http://profile:7777/health"),
    ]


async def _probe_tcp(host: str, port: int, timeout: float = 2.0) -> tuple[bool, float | None, str]:
    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001 - close errors are irrelevant here
            pass
        return True, round((loop.time() - start) * 1000, 1), "tcp connect ok"
    except (OSError, asyncio.TimeoutError) as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


async def _probe_http(url: str, timeout: float = 3.0) -> tuple[bool, float | None, str]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
        return (200 <= r.status_code < 400), round(r.elapsed.total_seconds() * 1000, 1), f"HTTP {r.status_code}"
    except httpx.HTTPError as exc:
        return False, None, f"{type(exc).__name__}: {exc}"


async def probe_services() -> list[ServiceState]:
    async def one(name: str, host: str, port: int, health: str | None) -> ServiceState:
        if health:
            ok, lat, detail = await _probe_http(health)
            if ok:
                return ServiceState(name, "http", health, True, detail, lat)
            # fall back to a bare TCP check so we can distinguish "down" from
            # "up but health endpoint unhappy".
            tcp_ok, tcp_lat, tcp_detail = await _probe_tcp(host, port)
            return ServiceState(name, "http", health, False, f"{detail}; tcp: {tcp_detail}", tcp_lat)
        ok, lat, detail = await _probe_tcp(host, port)
        return ServiceState(name, "tcp", f"{host}:{port}", ok, detail, lat)

    return list(await asyncio.gather(*(one(*t) for t in _targets())))


async def system_status() -> dict:
    services = await probe_services()
    all_ok = all(s.online for s in services)
    degraded = [s.name for s in services if not s.online]
    return {
        "operational": all_ok,
        "state": "operational" if all_ok else "degraded",
        "degraded_services": degraded,
        "services": [s.__dict__ for s in services],
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
