"""
Doctor schemas for listing and availability.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time
from pydantic import BaseModel

from app.schemas.auth import UserResponse


class DoctorWorkingHoursResponse(BaseModel):
    id: uuid.UUID
    day_of_week: int
    start_time: time
    end_time: time
    is_working: bool

    model_config = {"from_attributes": True}


class DoctorResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    specialisation: str
    bio: str | None = None
    consultation_fee: float | None = None
    slot_duration_minutes: int
    timezone: str
    user: UserResponse
    working_hours: list[DoctorWorkingHoursResponse]

    model_config = {"from_attributes": True}


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    status: str  # "AVAILABLE", "HELD", "BOOKED"


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: uuid.UUID
    date: date
    slots: list[TimeSlot]
