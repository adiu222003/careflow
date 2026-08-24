import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.notification import NotificationJob, NotificationJobStatus

try:
    import resend
    HAS_RESEND = True
except ImportError:
    HAS_RESEND = False

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        if HAS_RESEND and self.settings.resend_api_key:
            resend.api_key = self.settings.resend_api_key
            self.client = resend  # type: ignore
        else:
            self.client = None  # type: ignore

    async def _send_email(self, to: str, subject: str, html_body: str) -> None:
        if not self.settings.enable_email or not self.client:
            logger.info(f"Mock sending email to {to}: {subject}")
            return

        import asyncio
        params = {
            "from": self.settings.email_from,
            "to": [to],
            "subject": subject,
            "html": html_body,
        }

        await asyncio.to_thread(self.client.Emails.send, params)  # type: ignore

    async def _process_job(self, job: NotificationJob) -> None:
        """Processes a single notification job."""
        try:
            template = job.payload.get("template", "default")
            subject = f"CareFlow Notification: {job.type.value}"
            body = f"<p>This is a notification for {job.type.value}. Template: {template}</p>"

            await self._send_email(job.recipient, subject, body)

            job.status = NotificationJobStatus.SENT
            job.last_error = None
            logger.info(f"Successfully processed notification job {job.id}")

        except Exception as e:
            logger.error(f"Failed to process notification job {job.id}: {e}")
            job.attempts += 1
            job.last_error = str(e)

            if job.attempts >= 5:
                job.status = NotificationJobStatus.FAILED
            else:
                # Exponential backoff (e.g. 5m, 15m, 45m...)
                backoff_minutes = 5 ** job.attempts
                job.next_attempt_at = datetime.now(UTC) + timedelta(minutes=backoff_minutes)
                job.status = NotificationJobStatus.PENDING

    async def process_pending_jobs(self, batch_size: int = 50) -> int:
        """
        Fetches and processes pending notification jobs.
        Uses SELECT ... FOR UPDATE SKIP LOCKED to allow concurrent workers.
        """
        now = datetime.now(UTC)

        # We find PENDING jobs that are due
        stmt = (
            select(NotificationJob)
            .where(
                NotificationJob.status == NotificationJobStatus.PENDING,
                NotificationJob.next_attempt_at <= now
            )
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )

        result = await self.db.execute(stmt)
        jobs = result.scalars().all()

        if not jobs:
            return 0

        logger.info(f"Found {len(jobs)} pending notification jobs to process")

        for job in jobs:
            # Mark as processing so it doesn't get picked up again immediately if we yield
            job.status = NotificationJobStatus.PROCESSING

        await self.db.commit()

        # Now process them
        processed = 0
        for job in jobs:
            await self._process_job(job)
            processed += 1

        await self.db.commit()
        return processed
