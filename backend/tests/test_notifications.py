from unittest.mock import patch

import pytest

from app.models.notification import NotificationJob, NotificationJobStatus, NotificationJobType
from app.services.notification_service import NotificationService


@pytest.mark.asyncio
async def test_process_pending_jobs(db_session):
    # Insert a fake job
    job = NotificationJob(
        type=NotificationJobType.APPOINTMENT_CONFIRMATION_PATIENT,
        recipient="patient@careflow.demo",
        payload={"template": "appointment_confirmed"}
    )
    db_session.add(job)
    await db_session.commit()

    # Process it
    service = NotificationService(db_session)

    with patch.object(service, '_send_email') as mock_send:
        processed = await service.process_pending_jobs()

    assert processed >= 1
    mock_send.assert_called()

    # Check status
    await db_session.refresh(job)
    assert job.status == NotificationJobStatus.SENT

@pytest.mark.asyncio
async def test_process_job_failure_retry(db_session):
    job = NotificationJob(
        type=NotificationJobType.APPOINTMENT_CONFIRMATION_PATIENT,
        recipient="patient@careflow.demo",
        payload={}
    )
    db_session.add(job)
    await db_session.commit()

    service = NotificationService(db_session)

    with patch.object(service, '_send_email', side_effect=Exception("SMTP Error")):
        processed = await service.process_pending_jobs()

    assert processed == 1

    # Check status
    await db_session.refresh(job)
    assert job.status == NotificationJobStatus.PENDING
    assert job.attempts == 1
    assert "SMTP Error" in job.last_error
    assert job.next_attempt_at is not None

@pytest.mark.asyncio
async def test_process_job_failure_max_retries(db_session):
    job = NotificationJob(
        type=NotificationJobType.APPOINTMENT_CONFIRMATION_PATIENT,
        recipient="patient@careflow.demo",
        payload={},
        attempts=4  # this is the 5th attempt
    )
    db_session.add(job)
    await db_session.commit()

    service = NotificationService(db_session)

    with patch.object(service, '_send_email', side_effect=Exception("Final Error")):
        processed = await service.process_pending_jobs()

    assert processed == 1

    # Check status
    await db_session.refresh(job)
    assert job.status == NotificationJobStatus.FAILED
    assert job.attempts == 5
    assert "Final Error" in job.last_error
