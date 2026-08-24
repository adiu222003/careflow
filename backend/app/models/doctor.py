"""
Doctor-related ORM models:
  - DoctorProfile
  - DoctorWorkingHours
  - DoctorLeave
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.appointment import Appointment, AppointmentHold
    from app.models.user import User


import enum
import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DayOfWeek(int, enum.Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    specialisation: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    consultation_fee: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="doctor_profile")  # noqa: F821
    working_hours: Mapped[list[DoctorWorkingHours]] = relationship(
        "DoctorWorkingHours", back_populates="doctor", cascade="all, delete-orphan"
    )
    leaves: Mapped[list[DoctorLeave]] = relationship(
        "DoctorLeave", back_populates="doctor", cascade="all, delete-orphan"
    )
    appointments: Mapped[list[Appointment]] = relationship(  # noqa: F821
        "Appointment", back_populates="doctor"
    )
    appointment_holds: Mapped[list[AppointmentHold]] = relationship(  # noqa: F821
        "AppointmentHold", back_populates="doctor"
    )

    def __repr__(self) -> str:
        return f"<DoctorProfile id={self.id} specialisation={self.specialisation}>"


class DoctorWorkingHours(Base):
    __tablename__ = "doctor_working_hours"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon, 6=Sun
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_working: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    doctor: Mapped[DoctorProfile] = relationship("DoctorProfile", back_populates="working_hours")


class DoctorLeave(Base):
    __tablename__ = "doctor_leaves"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("doctor_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    doctor: Mapped[DoctorProfile] = relationship("DoctorProfile", back_populates="leaves")
