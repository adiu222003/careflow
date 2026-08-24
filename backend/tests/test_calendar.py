import uuid
from datetime import UTC

import pytest
from sqlalchemy import select

from app.models.calendar import CalendarEvent, CalendarEventStatus
from app.services.calendar_service import CalendarService


@pytest.mark.asyncio
async def test_encrypt_decrypt_token(db_session, monkeypatch):
    monkeypatch.setattr("app.services.calendar_service.HAS_GOOGLE", True)

    # We need a 32-url-safe base64 string
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key().decode()
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", test_key)
    monkeypatch.setenv("ENABLE_GOOGLE_CALENDAR", "true")

    # recreate settings
    from app.core.config import Settings
    test_settings = Settings()

    service = CalendarService(db_session)
    service.settings = test_settings
    service.enabled = True
    service.fernet = Fernet(test_settings.token_encryption_key.encode())

    original = "my_secret_token"
    encrypted = service.encrypt_token(original)

    assert encrypted != original
    decrypted = service.decrypt_token(encrypted)
    assert decrypted == original

@pytest.mark.asyncio
async def test_get_authorization_url_mock(db_session):
    service = CalendarService(db_session)
    service.enabled = False

    uid = uuid.uuid4()
    url = service.get_authorization_url(uid)
    assert "mock-oauth" in url
    assert str(uid) in url

@pytest.mark.asyncio
async def test_sync_pending_events_mock(db_session, seed_data):
    from datetime import datetime, timedelta

    from app.schemas.appointment import BookRequest, HoldRequest
    from app.services.appointment_service import AppointmentService

    patient_id = seed_data["patient_id"]
    doctor_id = seed_data["doctor_id"]

    # book an appointment
    appt_service = AppointmentService(db_session)
    start_t = datetime.now(UTC) + timedelta(days=2)
    end_t = start_t + timedelta(hours=1)

    hold_req = HoldRequest(doctor_id=doctor_id, start_time=start_t, end_time=end_t)
    hold = await appt_service.create_hold(patient_id, hold_req)

    book_req = BookRequest(hold_id=hold.id, symptoms="Checkup")
    appt = await appt_service.book_appointment(patient_id, book_req)

    # The book_appointment already creates CalendarEvent!
    service = CalendarService(db_session)
    service.enabled = False

    processed = await service.sync_pending_events()
    assert processed == 2

    stmt = select(CalendarEvent).where(CalendarEvent.appointment_id == appt.id)
    result = await db_session.execute(stmt)
    events = result.scalars().all()

    assert len(events) == 2
    for event in events:
        assert event.status == CalendarEventStatus.SYNCED
        assert "mock" in event.google_event_id
