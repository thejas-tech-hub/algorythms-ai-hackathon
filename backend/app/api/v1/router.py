"""
Aggregated v1 API router.
Owner: THEJAS

Single import point that collects all v1 sub-routers under /api/v1.
The app factory only needs to include this one router.
"""

from fastapi import APIRouter

from app.api.v1 import health, candidates, interviews

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(candidates.router)
router.include_router(interviews.router)
