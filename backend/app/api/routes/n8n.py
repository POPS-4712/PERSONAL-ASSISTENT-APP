from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.models import User
from app.services.n8n import N8nError, N8nService, get_n8n_service

router = APIRouter(prefix="/n8n", tags=["n8n"])


async def _run(awaitable):
    try:
        return await awaitable
    except N8nError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})


@router.get("/health")
async def health(
    user: User = Depends(get_current_user), n8n: N8nService = Depends(get_n8n_service)
):
    # health never raises for auth/connectivity — it reports them
    return await n8n.health()


@router.get("/workflows")
async def list_workflows(
    active: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return {"data": await _run(n8n.list_workflows(active=active, limit=limit))}


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return await _run(n8n.get_workflow(workflow_id))


@router.post("/workflows/{workflow_id}/activate")
async def activate(
    workflow_id: str,
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return await _run(n8n.activate(workflow_id))


@router.post("/workflows/{workflow_id}/deactivate")
async def deactivate(
    workflow_id: str,
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return await _run(n8n.deactivate(workflow_id))


@router.post("/workflows/{workflow_id}/run")
async def run(
    workflow_id: str,
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return await _run(n8n.run_workflow(workflow_id))


@router.get("/executions")
async def list_executions(
    workflow_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, pattern="^(success|error|waiting)$"),
    limit: int = Query(default=50, ge=1, le=250),
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return {
        "data": await _run(
            n8n.list_executions(workflow_id=workflow_id, status=status, limit=limit)
        )
    }


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    include_data: bool = Query(default=False),
    user: User = Depends(get_current_user),
    n8n: N8nService = Depends(get_n8n_service),
):
    return await _run(n8n.get_execution(execution_id, include_data=include_data))
