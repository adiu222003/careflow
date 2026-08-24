from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter

from app.core.database import DBSession
from app.core.dependencies import CurrentUser
from app.schemas.common import success
from app.schemas.doctor import DoctorResponse
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get("", response_model=dict)
async def get_doctors(db: DBSession, current_user: CurrentUser) -> dict:
    service = DoctorService(db)
    doctors = await service.get_doctors()
    # Map to schema
    return success([DoctorResponse.model_validate(d).model_dump() for d in doctors])


@router.get("/{doctor_id}/availability", response_model=dict)
async def get_availability(
    doctor_id: uuid.UUID,
    start_date: date,
    end_date: date,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    service = DoctorService(db)
    availability = await service.get_availability(doctor_id, start_date, end_date)
    return success(availability)
