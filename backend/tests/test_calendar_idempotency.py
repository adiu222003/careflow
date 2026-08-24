import uuid
import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy import select
from app.services.calendar_service import CalendarService
from app.models.calendar import OAuthToken, CalendarEvent, CalendarEventStatus, CalendarOperation
from app.models.appointment import Appointment
from datetime import datetime, timedelta, timezone

@pytest.mark.asyncio
async def test_calendar_idempotency_scenarios(db_session, seed_data):
    from app.services.appointment_service import AppointmentService
    from app.schemas.appointment import HoldRequest, BookRequest
    
    patient_id = seed_data["patient_id"]
    doctor_id = seed_data["doctor_id"]
    
    appt_service = AppointmentService(db_session)
    start_t = datetime.now(timezone.utc) + timedelta(days=2)
    end_t = start_t + timedelta(hours=1)
    
    hold_req = HoldRequest(doctor_id=doctor_id, start_time=start_t, end_time=end_t)
    hold = await appt_service.create_hold(patient_id, hold_req)
    book_req = BookRequest(hold_id=hold.id, symptoms="Checkup")
    appt = await appt_service.book_appointment(patient_id, book_req)
    
    # Enable service manually and mock credentials
    service = CalendarService(db_session)
    service.enabled = True
    
    from unittest.mock import AsyncMock
    mock_creds = MagicMock()
    service.get_credentials = AsyncMock(return_value=mock_creds)
    
    # We will simulate Google API calls using MagicMock
    mock_events = MagicMock()
    mock_service = MagicMock()
    mock_service.events.return_value = mock_events
    
    with patch("app.services.calendar_service.build", return_value=mock_service):
        
        # Test A: normal create
        mock_events.insert.return_value.execute.return_value = {"id": "test_id"}
        processed = await service.sync_pending_events()
        # 2 events were pending (patient, doctor). Both should be SYNCED.
        
        assert processed == 2
        
        stmt = select(CalendarEvent).where(CalendarEvent.appointment_id == appt.id)
        result = await db_session.execute(stmt)
        events = result.scalars().all()
        assert events[0].status == CalendarEventStatus.SYNCED
        
        # Manually create another CREATE event to simulate retry
        evt = CalendarEvent(
            appointment_id=appt.id,
            user_id=patient_id,
            operation=CalendarOperation.CREATE,
            status=CalendarEventStatus.PENDING,
            idempotency_key="mock_key_1"
        )
        db_session.add(evt)
        await db_session.commit()
        
        # Test C: timeout after remote create (409 Conflict)
        from googleapiclient.errors import HttpError
        mock_resp = MagicMock()
        mock_resp.status = 409
        mock_events.insert.return_value.execute.side_effect = HttpError(mock_resp, b"Conflict")
        
        processed = await service.sync_pending_events()
        
        await db_session.refresh(evt)
        assert evt.status == CalendarEventStatus.SYNCED
        assert evt.google_event_id == evt.id.hex
        
        # Test D: update retry (404 Not Found)
        evt2 = CalendarEvent(
            appointment_id=appt.id,
            user_id=patient_id,
            operation=CalendarOperation.UPDATE,
            status=CalendarEventStatus.PENDING,
            google_event_id=evt.id.hex,
            idempotency_key="mock_key_2"
        )
        db_session.add(evt2)
        await db_session.commit()
        
        mock_resp.status = 404
        mock_events.patch.return_value.execute.side_effect = HttpError(mock_resp, b"Not Found")
        mock_events.insert.return_value.execute.side_effect = None # Clear side effect for insert
        mock_events.insert.return_value.execute.return_value = {"id": evt.id.hex}
        
        processed = await service.sync_pending_events()
        await db_session.refresh(evt2)
        assert evt2.status == CalendarEventStatus.SYNCED
        
        # Test E: cancellation retry (404 Not Found)
        evt3 = CalendarEvent(
            appointment_id=appt.id,
            user_id=patient_id,
            operation=CalendarOperation.DELETE,
            status=CalendarEventStatus.PENDING,
            google_event_id=evt.id.hex,
            idempotency_key="mock_key_3"
        )
        db_session.add(evt3)
        await db_session.commit()
        
        mock_resp.status = 404
        mock_events.delete.return_value.execute.side_effect = HttpError(mock_resp, b"Not Found")
        
        processed = await service.sync_pending_events()
        await db_session.refresh(evt3)
        assert evt3.status == CalendarEventStatus.CANCELLED
