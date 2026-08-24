"""
Internal job processing endpoint.
Protected by X-Internal-Secret header — called by GitHub Actions scheduler.
Processes due notification jobs, medication reminders, calendar retries,
and expired slot holds.
Idempotent: safe to call multiple times.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import get_settings
from app.core.database import DBSession
from app.core.logging import get_logger

router = APIRouter(prefix="/internal", tags=["Internal"])
logger = get_logger(__name__)


@router.post("/jobs/process")
async def process_jobs(
    db: DBSession,
    x_internal_secret: str | None = Header(default=None),
) -> dict:
    """
    Process all due background jobs.
    - Notification jobs (email via Resend)
    - Medication reminder jobs
    - Calendar sync jobs (Google Calendar)
    - Expired appointment holds → EXPIRED

    Called by GitHub Actions scheduler every ~5 minutes.
    Uses SELECT FOR UPDATE SKIP LOCKED for safe concurrent execution.
    """
    settings = get_settings()
    if not x_internal_secret or x_internal_secret != settings.internal_job_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid or missing internal secret."},
        )

    # Placeholder: full implementation in Stage 5
    from app.services.notification_service import NotificationService
    from app.services.calendar_service import CalendarService
    
    notification_service = NotificationService(db)
    notifications_processed = await notification_service.process_pending_jobs()
    
    calendar_service = CalendarService(db)
    calendar_events_processed = await calendar_service.sync_pending_events()
    
    results = {
        "notification_jobs_processed": notifications_processed,
        "medication_reminders_processed": 0,
        "calendar_jobs_processed": calendar_events_processed,
        "holds_expired": 0,
    }

    logger.info("Job processor triggered. Results: %s", results)
    return {"success": True, "data": results}
