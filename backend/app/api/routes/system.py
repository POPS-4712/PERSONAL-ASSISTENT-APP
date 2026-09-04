
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_current_user
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas.system import HealthOut, HostMetricsOut, SystemStatusOut
from app.services.logbus import _order, bus
from app.services.metrics import as_dict, collect_host_metrics
from app.services.services_probe import system_status

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    """Liveness + readiness for the backend itself. Used by the installer and by
    Docker's healthcheck.
    """
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception as exc:  # noqa: BLE001 - report, don't crash the probe
        database = f"error: {type(exc).__name__}"
    problems = settings.validate_runtime()
    status = "ok" if database == "ok" and not problems else "degraded"
    return HealthOut(
        status=status,
        version=__version__,
        environment=settings.environment,
        database=database,
        problems=problems,
    )


@router.get("/system/status", response_model=SystemStatusOut)
async def status() -> SystemStatusOut:
    """Live probe of every service in the stack.

    Cheap enough to poll: cached provider verdicts are reused. Use
    `POST /system/check` for a forced, uncached re-probe.
    """
    return SystemStatusOut.model_validate(await system_status())


@router.post("/system/check", response_model=SystemStatusOut)
async def check(_: User = Depends(get_current_user)) -> SystemStatusOut:
    """Force a real, uncached re-probe of every service (CHECK SERVICES).

    Authenticated because it makes the backend originate outbound requests to
    every configured endpoint; leaving that open would let anyone use the API
    as a traffic amplifier.
    """
    return SystemStatusOut.model_validate(await system_status(force=True))


@router.get("/system/metrics", response_model=HostMetricsOut)
def metrics() -> HostMetricsOut:
    """Real host/container resource metrics."""
    return HostMetricsOut.model_validate(as_dict(collect_host_metrics()))


@router.get("/logs")
def logs(
    level: str = Query(default="INFO"),
    limit: int = Query(default=100, ge=1, le=500),
    source: str | None = Query(default=None),
    _: User = Depends(get_current_user),
) -> dict:
    """Recent structured log lines (secrets already scrubbed). The live stream
    is `WS /ws/logs`; this is the point-in-time backlog.
    """
    threshold = _order(level.upper())
    items = [
        e
        for e in list(bus._ring)
        if _order(e["level"]) >= threshold and (source is None or source in e["source"])
    ]
    return {"data": items[-limit:], "count": len(items)}
