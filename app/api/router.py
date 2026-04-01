from fastapi import APIRouter

from app.api.routes_health import router as health_router
from app.api.routes_ignored import router as ignored_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_stats import router as stats_router
from app.api.routes_sync import router as sync_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_router.include_router(sync_router, prefix="/sync", tags=["sync"])
api_router.include_router(stats_router, prefix="/stats", tags=["stats"])
api_router.include_router(ignored_router, prefix="/ignored-emails", tags=["ignored-emails"])
