"""
Health check endpoint — no auth required.
Returns application status and feature flag states.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "CareFlow API",
        "version": "1.0.0",
        "features": {
            "llm": settings.enable_llm,
            "email": settings.enable_email,
            "google_calendar": settings.enable_google_calendar,
        },
        "environment": settings.environment,
    }
