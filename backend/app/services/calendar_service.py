import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.calendar import CalendarEvent, CalendarEventStatus, CalendarOperation, OAuthToken
from app.models.appointment import Appointment
from app.models.user import User, Role

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    import google.auth.transport.requests
    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

logger = logging.getLogger(__name__)

class CalendarService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.enabled = HAS_GOOGLE and self.settings.enable_google_calendar and bool(self.settings.token_encryption_key)
        
        if self.enabled:
            # Note: fernet key must be 32 url-safe base64-encoded bytes
            try:
                self.fernet = Fernet(self.settings.token_encryption_key.encode())
            except Exception as e:
                logger.error(f"Failed to initialize Fernet with provided key: {e}")
                self.enabled = False

    def encrypt_token(self, token: str) -> str:
        if not self.enabled:
            return token
        return self.fernet.encrypt(token.encode()).decode()

    def decrypt_token(self, encrypted_token: str) -> str:
        if not self.enabled:
            return encrypted_token
        return self.fernet.decrypt(encrypted_token.encode()).decode()

    def get_authorization_url(self, user_id: uuid.UUID) -> str:
        if not self.enabled:
            return "http://localhost:3000/mock-oauth?state=" + str(user_id)
            
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=[self.settings.google_calendar_scope],
            redirect_uri=self.settings.google_redirect_uri,
        )
        
        # We pass user_id in state to link it on callback
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=str(user_id)
        )
        return auth_url

    async def exchange_code_for_tokens(self, code: str, user_id: uuid.UUID) -> None:
        if not self.enabled:
            # Mock behavior
            return await self._store_mock_token(user_id)
            
        import asyncio
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=[self.settings.google_calendar_scope],
            redirect_uri=self.settings.google_redirect_uri,
        )
        
        # Exchange code synchronously in a thread
        await asyncio.to_thread(flow.fetch_token, code=code)
        creds = flow.credentials
        
        # Store in DB
        await self._store_tokens(
            user_id=user_id,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expiry=creds.expiry
        )

    async def _store_mock_token(self, user_id: uuid.UUID) -> None:
        await self._store_tokens(user_id, "mock_access", "mock_refresh", datetime.now(timezone.utc) + timedelta(days=30))

    async def _store_tokens(self, user_id: uuid.UUID, access_token: str, refresh_token: str | None, expiry: datetime | None) -> None:
        # Check if already exists
        stmt = select(OAuthToken).where(OAuthToken.user_id == user_id)
        result = await self.db.execute(stmt)
        token_record = result.scalars().first()
        
        if not token_record:
            token_record = OAuthToken(user_id=user_id)
            self.db.add(token_record)
            
        token_record.encrypted_access_token = self.encrypt_token(access_token) if access_token else None
        
        if refresh_token:
            token_record.encrypted_refresh_token = self.encrypt_token(refresh_token)
            
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
            
        token_record.expires_at = expiry
        token_record.updated_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def get_credentials(self, user_id: uuid.UUID) -> Optional[Credentials]:
        stmt = select(OAuthToken).where(OAuthToken.user_id == user_id)
        result = await self.db.execute(stmt)
        token_record = result.scalars().first()
        
        if not token_record or not token_record.encrypted_refresh_token:
            return None
            
        refresh_token = self.decrypt_token(token_record.encrypted_refresh_token)
        access_token = self.decrypt_token(token_record.encrypted_access_token) if token_record.encrypted_access_token else None
        
        # If naive datetime, make it aware
        expiry = token_record.expires_at
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
            
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            scopes=[self.settings.google_calendar_scope],
            expiry=expiry.replace(tzinfo=None) if expiry else None # google-auth expects naive datetime
        )
        return creds

    async def sync_pending_events(self, batch_size: int = 20) -> int:
        """
        Process PENDING calendar jobs.
        Called by the internal processor.
        """
        stmt = select(CalendarEvent).where(
            CalendarEvent.status == CalendarEventStatus.PENDING
        ).limit(batch_size).with_for_update(skip_locked=True)
        
        result = await self.db.execute(stmt)
        events = result.scalars().all()
        
        if not events:
            return 0
            
        for event in events:
            try:
                await self._process_event(event)
            except Exception as e:
                logger.error(f"Failed to process calendar event {event.id}: {e}")
                event.status = CalendarEventStatus.FAILED
                
        await self.db.commit()
        return len(events)

    async def _process_event(self, event: CalendarEvent) -> None:
        """Sync a single event to Google Calendar"""
        if not self.enabled:
            logger.info(f"Mock sync CalendarEvent {event.id} (Op: {event.operation.value})")
            event.status = CalendarEventStatus.SYNCED
            if not event.google_event_id:
                event.google_event_id = "mock_google_id_" + str(event.appointment_id)
            return

        creds = await self.get_credentials(event.user_id)
        if not creds:
            logger.info(f"User {event.user_id} has no calendar connected. Marking as CANCELLED.")
            event.status = CalendarEventStatus.CANCELLED
            return
            
        import asyncio
        service = build("calendar", "v3", credentials=creds)
        
        appt = await self.db.get(Appointment, event.appointment_id)
        if not appt:
            event.status = CalendarEventStatus.CANCELLED
            return
            
        user = await self.db.get(User, event.user_id)
        
        # Build event body
        title = "CareFlow Appointment"
        if user and user.role == Role.PATIENT:
            title = "Doctor Appointment via CareFlow"
        elif user and user.role == Role.DOCTOR:
            title = "Patient Consultation via CareFlow"
            
        body = {
            "summary": title,
            "description": f"Appointment Reference: {appt.booking_reference}",
            "start": {"dateTime": appt.start_time.isoformat()},
            "end": {"dateTime": appt.end_time.isoformat()},
        }
        
        try:
            if event.operation == CalendarOperation.CREATE:
                if event.google_event_id:
                    event.status = CalendarEventStatus.SYNCED
                    return
                
                # Use the database UUID as a deterministic, base32hex-compatible Google Event ID
                # UUID hex is 32 chars of 0-9a-f. Google allows 0-9a-v.
                deterministic_id = event.id.hex
                body["id"] = deterministic_id
                
                try:
                    res = await asyncio.to_thread(
                        service.events().insert(calendarId="primary", body=body).execute
                    )
                    event.google_event_id = res.get("id")
                    event.status = CalendarEventStatus.SYNCED
                except Exception as ex:
                    if "409" in str(ex):
                        # The uncertain CREATE actually succeeded previously, but we didn't get the response.
                        logger.info(f"Event {deterministic_id} already exists (409 Conflict). Reconciling as SYNCED.")
                        event.google_event_id = deterministic_id
                        event.status = CalendarEventStatus.SYNCED
                        
                        # Optionally, patch it to ensure it's up to date
                        await asyncio.to_thread(
                            service.events().patch(calendarId="primary", eventId=deterministic_id, body=body).execute
                        )
                    else:
                        raise ex
                
            elif event.operation == CalendarOperation.UPDATE:
                if not event.google_event_id:
                    event.google_event_id = event.id.hex # Try our deterministic ID
                    
                try:
                    await asyncio.to_thread(
                        service.events().patch(calendarId="primary", eventId=event.google_event_id, body=body).execute
                    )
                    event.status = CalendarEventStatus.SYNCED
                except Exception as ex:
                    if "404" in str(ex):
                        # Missing remote event during update -> create it
                        logger.info("Event missing during UPDATE. Recreating.")
                        body["id"] = event.google_event_id
                        await asyncio.to_thread(
                            service.events().insert(calendarId="primary", body=body).execute
                        )
                        event.status = CalendarEventStatus.SYNCED
                    else:
                        raise ex
                
            elif event.operation == CalendarOperation.DELETE:
                if not event.google_event_id:
                    event.status = CalendarEventStatus.CANCELLED
                    return
                try:
                    await asyncio.to_thread(
                        service.events().delete(calendarId="primary", eventId=event.google_event_id).execute
                    )
                except Exception as ex:
                    # 404 already deleted
                    if "404" in str(ex):
                        pass
                    else:
                        raise ex
                event.status = CalendarEventStatus.CANCELLED
                
            event.last_synced_at = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Google Calendar API error: {e}")
            event.status = CalendarEventStatus.FAILED
