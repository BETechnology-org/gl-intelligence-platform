"""Health & status endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..config import settings

router = APIRouter()


@router.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "BL/GL Intelligence API",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
