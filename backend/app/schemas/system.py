from __future__ import annotations

from pydantic import BaseModel


class ServiceStateOut(BaseModel):
    name: str
    kind: str  # db | http | data | provider
    target: str
    # online | configured | degraded | invalid | offline | not_configured | unknown
    status: str
    # kept for backward compatibility: true for online/configured, false for
    # offline/invalid, null for everything else
    online: bool | None
    # whether this environment has the service set up at all - the distinction
    # the dashboard needs to avoid showing "offline" for something nobody asked for
    configured: bool = False
    detail: str
    latency_ms: float | None
    checked_at: str = ""
    meta: dict = {}


class SystemStatusOut(BaseModel):
    operational: bool
    state: str
    degraded_services: list[str]
    not_configured_services: list[str] = []
    services: list[ServiceStateOut]
    checked_at: str


class HostMetricsOut(BaseModel):
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_free_gb: float
    disk_total_gb: float
    load_avg_1m: float | None
    uptime_seconds: float
    sampled_at: str


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    problems: list[str]
