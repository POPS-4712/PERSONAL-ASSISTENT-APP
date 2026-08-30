"""Host resource metrics. Real numbers from psutil; no fabricated values.

Inside the backend container these reflect the container's cgroup view when the
kernel exposes it, otherwise the host. That is the honest best we can do without
a privileged agent, and it is what the dashboard shows.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import psutil

# psutil.cpu_percent needs an interval or two calls; we prime it once at import
# so the first request returns a real delta instead of 0.0.
psutil.cpu_percent(interval=None)
_primed_at = time.monotonic()


@dataclass
class HostMetrics:
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


def collect_host_metrics(cpu_sample_seconds: float = 0.15) -> HostMetrics:
    vm = psutil.virtual_memory()
    du = psutil.disk_usage("/")
    try:
        load1 = psutil.getloadavg()[0]
    except (AttributeError, OSError):
        load1 = None
    # A short blocking sample gives a real utilisation figure; the route runs in
    # a threadpool so this does not stall the event loop.
    return HostMetrics(
        cpu_percent=round(psutil.cpu_percent(interval=cpu_sample_seconds), 1),
        memory_percent=round(vm.percent, 1),
        memory_used_mb=round((vm.total - vm.available) / 1024 / 1024, 1),
        memory_total_mb=round(vm.total / 1024 / 1024, 1),
        disk_percent=round(du.percent, 1),
        disk_free_gb=round(du.free / 1024 / 1024 / 1024, 2),
        disk_total_gb=round(du.total / 1024 / 1024 / 1024, 2),
        load_avg_1m=round(load1, 2) if load1 is not None else None,
        uptime_seconds=round(time.time() - psutil.boot_time(), 0),
        sampled_at=_iso_now(),
    )


def _iso_now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).isoformat()


def as_dict(m: HostMetrics) -> dict:
    return asdict(m)
