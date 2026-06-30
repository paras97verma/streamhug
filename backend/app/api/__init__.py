"""API router aggregation.

All sub-routers are collected here.  The version prefix (e.g. ``/api/v1``)
is **not** set here — it is applied in ``main.py`` using the configured
``Settings.api_prefix`` so the version is never hardcoded.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.library import router as library_router
from app.api.metrics import router as metrics_router
from app.api.media import router as media_router
from app.api.stream import router as stream_router
from app.api.events import router as events_router
from app.api.config import router as config_router
from app.api.tracks import router as tracks_router
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.ws import router as ws_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(library_router)
api_router.include_router(media_router)
api_router.include_router(tracks_router)
api_router.include_router(stream_router)
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(events_router)
api_router.include_router(config_router)
api_router.include_router(metrics_router)
api_router.include_router(ws_router)
