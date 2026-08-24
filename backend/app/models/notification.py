"""
Notification and medication reminder ORM models.
Implements the outbox pattern: jobs are written inside the appointment transaction
and processed asynchronously by the background worker.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.prescription import PrescriptionItem


import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class NotificationJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"


class NotificationJobType(str, enum.Enum):
    APPOINTMENT_CONFIRMATION_PATIENT = "APPOINTMENT_CONFIRMATION_PATIENT"
    APPOINTMENT_CONFIRMATION_DOCTOR = "APPOINTMENT_CONFIRMATION_DOCTOR"
    APPOINTMENT_REMINDER_PATIENT = "APPOINTMENT_REMINDER_PATIENT"
    APPOINTMENT_REMINDER_DOCTOR = "APPOINTMENT_REMINDER_DOCTOR"
    APPOINTMENT_CANCELLATION_PATIENT = "APPOINTMENT_CANCELLATION_PATIENT"
    APPOINTMENT_CANCELLATION_DOCTOR = "APPOINTMENT_CANCELLATION_DOCTOR"
    DOCTOR_LEAVE_CANCELLATION = "DOCTOR_LEAVE_CANCELLATION"
    POST_VISIT_SUMMARY = "POST_VISIT_SUMMARY"
    MEDICATION_REMINDER = "MEDICATION_REMINDER"


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationJob(Base):
    """
    Outbox-pattern notification job. Written inside the appointment transaction;
    executed asynchronously by the worker. Supports retry with exponential backoff.
    """
    __tablename__ = "notification_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[NotificationJobType] = mapped_column(
        Enum(NotificationJobType), nullable=False, index=True
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)  # email address
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    status: Mapped[NotificationJobStatus] = mapped_column(
        Enum(NotificationJobStatus), nullable=False, default=NotificationJobStatus.PENDING, index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    appointment: Mapped[Appointment | None] = relationship(  # noqa: F821
        "Appointment", back_populates="notification_jobs"
    )


class MedicationReminder(Base):
    """
    Scheduled medication reminder jobs generated from prescription items.
    Idempotency key: (prescription_item_id, scheduled_at) — unique constraint.
    """
    __tablename__ = "medication_reminders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prescription_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prescription_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    status: Mapped[ReminderStatus] = mapped_column(
        Enum(ReminderStatus), nullable=False, default=ReminderStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    prescription_item: Mapped[PrescriptionItem] = relationship(  # noqa: F821
        "PrescriptionItem", back_populates="reminders"
    )
