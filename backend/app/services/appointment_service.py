import uuid
from datetime import datetime, timezone, timedelta
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import selectinload

from app.models.appointment import Appointment, AppointmentHold, AppointmentStatus, HoldStatus
from app.models.doctor import DoctorProfile
from app.models.notification import NotificationJob, NotificationJobStatus, NotificationJobType
from app.models.calendar import CalendarEvent, CalendarEventStatus, CalendarOperation
from app.models.audit import AuditLog
from app.core.exceptions import (
    NotFoundError, 
    SlotUnavailableError, 
    HoldExpiredError,
    ConflictError
)
from app.schemas.appointment import HoldRequest, BookRequest, RescheduleRequest


class AppointmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_hold(self, patient_id: uuid.UUID, request: HoldRequest) -> AppointmentHold:
        """
        Create a 5-minute hold on a slot.
        If it fails because of the PostgreSQL exclusion constraint (overlapping HELD slot),
        it throws a SlotUnavailableError.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=5)
        
        # Check if doctor exists and slot duration matches
        doctor = await self.db.get(DoctorProfile, request.doctor_id)
        if not doctor:
            raise NotFoundError("Doctor not found.")
            
        # First quickly check if there's already a CONFIRMED appointment
        # The DB constraint protects us anyway, but this gives a clearer error
        stmt = select(Appointment).where(
            Appointment.doctor_id == request.doctor_id,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.start_time < request.end_time,
            Appointment.end_time > request.start_time
        )
        res = await self.db.execute(stmt)
        if res.scalar_one_or_none():
            raise SlotUnavailableError()

        hold = AppointmentHold(
            doctor_id=request.doctor_id,
            patient_id=patient_id,
            start_time=request.start_time,
            end_time=request.end_time,
            expires_at=expires_at,
            status=HoldStatus.HELD
        )
        
        self.db.add(hold)
        
        # Log the hold
        self.db.add(AuditLog(
            actor_user_id=patient_id,
            action="HOLD_CREATED",
            entity_type="AppointmentHold",
            entity_id=hold.id,
            extra={"doctor_id": str(request.doctor_id), "start": request.start_time.isoformat()}
        ))
        
        try:
            await self.db.commit()
            await self.db.refresh(hold)
            return hold
        except (IntegrityError, DBAPIError):
            await self.db.rollback()
            raise SlotUnavailableError("Slot is no longer available.")

    async def book_appointment(self, patient_id: uuid.UUID, request: BookRequest) -> Appointment:
        """
        Convert a HOLD into a CONFIRMED appointment.
        Uses a transaction to ensure atomicity with notification and calendar outbox jobs.
        """
        hold = await self.db.get(AppointmentHold, request.hold_id)
        if not hold:
            raise NotFoundError("Hold not found.")
            
        if hold.patient_id != patient_id:
            raise ConflictError("Hold belongs to another patient.")
            
        if hold.status != HoldStatus.HELD:
            raise ConflictError("Hold is already processed or cancelled.")
            
        if hold.expires_at < datetime.now(timezone.utc):
            hold.status = HoldStatus.EXPIRED
            await self.db.commit()
            raise HoldExpiredError()

        # Update hold
        hold.status = HoldStatus.CONVERTED
        
        # Create appointment
        import secrets
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=hold.doctor_id,
            start_time=hold.start_time,
            end_time=hold.end_time,
            status=AppointmentStatus.CONFIRMED,
            symptoms=request.symptoms,
            booking_reference=secrets.token_urlsafe(8).upper()[:10]
        )
        self.db.add(appointment)
        
        # Flush to get the appointment ID for the foreign keys below
        try:
            await self.db.flush()
        except (IntegrityError, DBAPIError) as e:
            await self.db.rollback()
            if "uq_appointment_overlap" in str(e):
                raise SlotUnavailableError()
            raise ConflictError("Could not book appointment.")

        # We need patient email for the recipient field
        from app.models.user import User
        patient = await self.db.get(User, patient_id)
        if not patient:
            raise NotFoundError("Patient not found")

        # Outbox: Patient confirmation email
        self.db.add(NotificationJob(
            recipient=patient.email,
            appointment_id=appointment.id,
            type=NotificationJobType.APPOINTMENT_CONFIRMATION_PATIENT,
            status=NotificationJobStatus.PENDING,
            payload={"template": "appointment_confirmed_patient"}
        ))
        
        # Outbox: Calendar Sync (Patient & Doctor)
        self.db.add(CalendarEvent(
            user_id=patient_id,
            appointment_id=appointment.id,
            status=CalendarEventStatus.PENDING,
            operation=CalendarOperation.CREATE,
            idempotency_key=f"{appointment.id}_{patient_id}_CREATE"
        ))
        
        # Note: We need the doctor's user_id for their calendar sync
        doctor = await self.db.get(DoctorProfile, hold.doctor_id)
        if doctor:
            self.db.add(CalendarEvent(
                user_id=doctor.user_id,
                appointment_id=appointment.id,
                status=CalendarEventStatus.PENDING,
                operation=CalendarOperation.CREATE,
                idempotency_key=f"{appointment.id}_{doctor.user_id}_CREATE"
            ))

        # Audit
        self.db.add(AuditLog(
            actor_user_id=patient_id,
            action="APPOINTMENT_BOOKED",
            entity_type="Appointment",
            entity_id=appointment.id,
            extra={"doctor_id": str(hold.doctor_id), "start": hold.start_time.isoformat()}
        ))

        try:
            await self.db.commit()
            await self.db.refresh(appointment)
            return appointment
        except IntegrityError as e:
            await self.db.rollback()
            if "no_overlapping_confirmed_appointments" in str(e):
                raise SlotUnavailableError()
            raise ConflictError("Could not book appointment.")

    async def cancel_appointment(self, appointment_id: uuid.UUID, actor_id: uuid.UUID) -> Appointment:
        appt = await self.db.get(Appointment, appointment_id, options=[selectinload(Appointment.doctor)])
        if not appt:
            raise NotFoundError()
            
        appt.status = AppointmentStatus.CANCELLED
        
        # Get patient email
        from app.models.user import User
        patient = await self.db.get(User, appt.patient_id)
        recipient_email = patient.email if patient else "unknown@careflow.com"

        # Outbox notifications and calendar deletions
        self.db.add(NotificationJob(
            recipient=recipient_email,
            appointment_id=appt.id,
            type=NotificationJobType.APPOINTMENT_CANCELLATION_PATIENT,
            status=NotificationJobStatus.PENDING,
            payload={"template": "appointment_cancelled"}
        ))
        
        self.db.add(CalendarEvent(
            user_id=appt.patient_id,
            appointment_id=appt.id,
            status=CalendarEventStatus.PENDING,
            operation=CalendarOperation.DELETE,
            idempotency_key=f"{appt.id}_{appt.patient_id}_DELETE"
        ))
        
        if appt.doctor:
            self.db.add(CalendarEvent(
                user_id=appt.doctor.user_id,
                appointment_id=appt.id,
                status=CalendarEventStatus.PENDING,
                operation=CalendarOperation.DELETE,
                idempotency_key=f"{appt.id}_{appt.doctor.user_id}_DELETE"
            ))

        self.db.add(AuditLog(
            actor_user_id=actor_id,
            action="APPOINTMENT_CANCELLED",
            entity_type="Appointment",
            entity_id=appt.id
        ))
        
        await self.db.commit()
        await self.db.refresh(appt)
        return appt

    async def get_appointment(self, appointment_id: uuid.UUID) -> Appointment:
        appt = await self.db.get(Appointment, appointment_id)
        if not appt:
            raise NotFoundError()
        return appt

    async def submit_consultation(self, appointment_id: uuid.UUID, doctor_user_id: uuid.UUID, notes: str) -> Appointment:
        appt = await self.db.get(Appointment, appointment_id)
        if not appt:
            raise NotFoundError("Appointment not found")
            
        appt.doctor_notes = notes
        appt.status = AppointmentStatus.COMPLETED
        
        self.db.add(AuditLog(
            actor_user_id=doctor_user_id,
            action="DOCTOR_SUBMITTED_CONSULTATION",
            entity_type="Appointment",
            entity_id=appt.id
        ))
        
        await self.db.commit()
        await self.db.refresh(appt)
        return appt
