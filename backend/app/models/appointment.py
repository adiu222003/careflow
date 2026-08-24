"""
Appointment and AppointmentHold ORM models.

Key design:
  - AppointmentHold: temporary 5-minute reservation (HELD / EXPIRED / CONVERTED)
  - Appointment: final confirmed/completed/cancelled records only

Two PostgreSQL exclusion constraints prevent overlapping bookings:
  1. appointment_holds: no two HELD rows for same doctor + time range
  2. appointments: no two CONFIRMED rows for same doctor + time range

The DB constraint is the authoritative last line of defense; application-level
checks are a first filter only.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.doctor import DoctorProfile
    from app.models.user import User
    from app.models.prescription import Prescription
    from app.models.notification import NotificationJob
    from app.models.calendar import CalendarEvent


import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppointmentStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HoldStatus(str, enum.Enum):
    HELD = "HELD"
    EXPIRED = "EXPIRED"
    CONVERTED = "CONVERTED"


class UrgencyLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AIStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AppointmentHold(Base):
    """
    Temporary slot reservation created when a patient selects a slot.
    Expires after 5 minutes if not confirmed.
    """
    __tablename__ = "appointment_holds"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[HoldStatus] = mapped_column(
        Enum(HoldStatus), nullable=False, default=HoldStatus.HELD, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    doctor: Mapped[DoctorProfile] = relationship(  # noqa: F821
        "DoctorProfile", back_populates="appointment_holds"
    )
    patient: Mapped[User] = relationship("User")  # noqa: F821

    __table_args__ = (
        ExcludeConstraint(
            ("doctor_id", "="),
            (text("tstzrange(start_time, end_time)"), "&&"),
            where=text("status = 'HELD'"),
            name="uq_appointment_hold_overlap"
        ),
    )

    def is_active(self) -> bool:
        return self.status == HoldStatus.HELD and self.expires_at > datetime.now(UTC)


class Appointment(Base):
    """
    Confirmed/completed/cancelled appointments.
    Never hard-deleted — cancellation reason preserved for audit.
    """
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctor_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    booking_reference: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), nullable=False, default=AppointmentStatus.CONFIRMED, index=True
    )

    # Symptom data (raw patient input)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI pre-visit summary fields
    pre_visit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    urgency_level: Mapped[UrgencyLevel | None] = mapped_column(
        Enum(UrgencyLevel), nullable=True
    )
    pre_visit_ai_status: Mapped[AIStatus] = mapped_column(
        Enum(AIStatus), nullable=False, default=AIStatus.PENDING
    )

    # Doctor consultation
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_visit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_visit_ai_status: Mapped[AIStatus] = mapped_column(
        Enum(AIStatus), nullable=False, default=AIStatus.PENDING
    )

    # Cancellation
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    doctor: Mapped[DoctorProfile] = relationship(  # noqa: F821
        "DoctorProfile", back_populates="appointments"
    )
    patient: Mapped[User] = relationship("User")  # noqa: F821
    prescription: Mapped[Prescription | None] = relationship(  # noqa: F821
        "Prescription", back_populates="appointment", uselist=False
    )
    notification_jobs: Mapped[list[NotificationJob]] = relationship(  # noqa: F821
        "NotificationJob", back_populates="appointment"
    )
    calendar_events: Mapped[list[CalendarEvent]] = relationship(  # noqa: F821
        "CalendarEvent", back_populates="appointment"
    )

    def __repr__(self) -> str:
        return f"<Appointment id={self.id} ref={self.booking_reference} status={self.status}>"
        
    __table_args__ = (
        ExcludeConstraint(
            ("doctor_id", "="),
            (text("tstzrange(start_time, end_time)"), "&&"),
            where=text("status = 'CONFIRMED'"),
            name="uq_appointment_overlap"
        ),
    )
