from fastapi import APIRouter

from app.api.routes import auth, credentials, profiles, system

api_router = APIRouter(prefix="/api")
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(credentials.router)
