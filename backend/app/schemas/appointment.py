"""
Appointment schemas for holds, booking, and responses.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.appointment import AppointmentStatus


class HoldRequest(BaseModel):
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime


class HoldResponse(BaseModel):
    id: uuid.UUID = Field(alias="hold_id")
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    expires_at: datetime
    status: str

    model_config = {"from_attributes": True, "populate_by_name": True}


class BookRequest(BaseModel):
    hold_id: uuid.UUID
    symptoms: str = Field(..., max_length=1000)


class AppointmentResponse(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    symptoms: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RescheduleRequest(BaseModel):
    new_start_time: datetime
    new_end_time: datetime

class ConsultationRequest(BaseModel):
    doctor_notes: str = Field(..., min_length=5, max_length=5000, description="Raw doctor notes to be structured by AI.")
