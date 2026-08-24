from __future__ import annotations

import uuid
from fastapi import APIRouter, status, BackgroundTasks

from app.core.database import DBSession
from app.core.dependencies import PatientUser, CurrentUser, check_appointment_access
from app.schemas.common import success
from app.schemas.appointment import HoldRequest, HoldResponse, BookRequest, AppointmentResponse
from app.services.appointment_service import AppointmentService
from app.tasks.ai_tasks import process_pre_visit_summary

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.get("/my", response_model=dict)
async def list_my_appointments(
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    from sqlalchemy import select
    from app.models.appointment import Appointment
    
    if current_user.role == "PATIENT":
        stmt = select(Appointment).where(Appointment.patient_id == current_user.id).order_by(Appointment.start_time.desc())
    elif current_user.role == "DOCTOR":
        if not current_user.doctor_profile:
            return success([])
        stmt = select(Appointment).where(Appointment.doctor_id == current_user.doctor_profile.id).order_by(Appointment.start_time.desc())
    else:
        stmt = select(Appointment).order_by(Appointment.start_time.desc())
        
    result = await db.execute(stmt)
    appts = result.scalars().all()
    return success([AppointmentResponse.model_validate(a).model_dump() for a in appts])

@router.post("/hold", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_hold(
    request: HoldRequest,
    db: DBSession,
    current_user: PatientUser,
) -> dict:
    service = AppointmentService(db)
    hold = await service.create_hold(current_user.id, request)
    return success(HoldResponse.model_validate(hold).model_dump(by_alias=True))


@router.post("/book", response_model=dict, status_code=status.HTTP_201_CREATED)
async def book_appointment(
    request: BookRequest,
    db: DBSession,
    current_user: PatientUser,
    background_tasks: BackgroundTasks,
) -> dict:
    service = AppointmentService(db)
    appt = await service.book_appointment(current_user.id, request)
    background_tasks.add_task(process_pre_visit_summary, appt.id)
    return success(AppointmentResponse.model_validate(appt).model_dump())


@router.post("/{appointment_id}/cancel", response_model=dict)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    service = AppointmentService(db)
    appt = await service.get_appointment(appointment_id)
    
    # Check if current user is allowed to cancel this appointment
    check_appointment_access(appt, current_user)
    
    cancelled = await service.cancel_appointment(appointment_id, current_user.id)
    return success(AppointmentResponse.model_validate(cancelled).model_dump())


from app.schemas.appointment import ConsultationRequest
from app.tasks.ai_tasks import process_post_visit_summary
from app.core.dependencies import DoctorUser

@router.post("/{appointment_id}/consultation", response_model=dict)
async def submit_consultation(
    appointment_id: uuid.UUID,
    request: ConsultationRequest,
    db: DBSession,
    current_user: DoctorUser,
    background_tasks: BackgroundTasks,
) -> dict:
    service = AppointmentService(db)
    appt = await service.get_appointment(appointment_id)
    check_appointment_access(appt, current_user)
    
    appt = await service.submit_consultation(appointment_id, current_user.id, request.doctor_notes)
    
    background_tasks.add_task(process_post_visit_summary, appt.id)
    
    return success(AppointmentResponse.model_validate(appt).model_dump())
