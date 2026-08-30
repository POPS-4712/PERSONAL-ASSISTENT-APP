from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.db import get_db
from app.schemas.system import HealthOut, HostMetricsOut, SystemStatusOut
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
    """Live probe of every service in the stack."""
    return SystemStatusOut.model_validate(await system_status())


@router.get("/system/metrics", response_model=HostMetricsOut)
def metrics() -> HostMetricsOut:
    """Real host/container resource metrics."""
    return HostMetricsOut.model_validate(as_dict(collect_host_metrics()))
