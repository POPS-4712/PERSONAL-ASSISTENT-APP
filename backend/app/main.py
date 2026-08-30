from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api import api_router
from app.config import get_settings
from app.core.logging import configure_logging

log = logging.getLogger("automation_center")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging("DEBUG" if settings.debug else "INFO")
    problems = settings.validate_runtime()
    if problems:
        for p in problems:
            log.warning("BLOCKED BY: %s", p)
    log.info("Automation Center backend %s starting (env=%s)", __version__, settings.environment)
    yield
    log.info("Automation Center backend stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Automation Center API",
        version=__version__,
        description="Backend for the Automation Center control plane.",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_context(request: Request, call_next):
        correlation_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - convert to a clean 500, keep the trace in logs
            log.exception("unhandled error", extra={"correlation_id": correlation_id})
            return JSONResponse(
                status_code=500,
                content={"detail": "internal error", "correlation_id": correlation_id},
            )
        response.headers["x-request-id"] = correlation_id
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("x-frame-options", "DENY")
        response.headers.setdefault("referrer-policy", "no-referrer")
        return response

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"service": "automation-center-backend", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
