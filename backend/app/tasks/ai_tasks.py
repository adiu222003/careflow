import uuid
import logging
from app.core.database import AsyncSessionLocal
from app.models.appointment import Appointment, AIStatus
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)

async def process_pre_visit_summary(appointment_id: uuid.UUID) -> None:
    """
    Background task to generate AI summary for patient symptoms.
    """
    async with AsyncSessionLocal() as db:
        appointment = await db.get(Appointment, appointment_id)
        if not appointment or not appointment.symptoms:
            return
            
        if appointment.pre_visit_ai_status == AIStatus.SUCCESS:
            return

        service = AIService()
        try:
            summary = await service.generate_pre_visit_summary(appointment.symptoms)
            appointment.pre_visit_summary = summary.summary
            appointment.urgency_level = summary.urgency  # Note: ensure urgency matches the Enum exactly (Low, Medium, High)
            appointment.pre_visit_ai_status = AIStatus.SUCCESS
        except Exception as e:
            logger.error(f"Error in process_pre_visit_summary: {e}")
            appointment.pre_visit_ai_status = AIStatus.FAILED
            
        await db.commit()

async def process_post_visit_summary(appointment_id: uuid.UUID) -> None:
    """
    Background task to generate AI summary for doctor notes.
    """
    async with AsyncSessionLocal() as db:
        appointment = await db.get(Appointment, appointment_id)
        if not appointment or not appointment.doctor_notes:
            return
            
        if appointment.post_visit_ai_status == AIStatus.SUCCESS:
            return

        service = AIService()
        try:
            summary = await service.generate_post_visit_summary(appointment.doctor_notes)
            appointment.post_visit_summary = summary.structured_notes
            appointment.post_visit_ai_status = AIStatus.SUCCESS
        except Exception as e:
            logger.error(f"Error in process_post_visit_summary: {e}")
            appointment.post_visit_ai_status = AIStatus.FAILED
            
        await db.commit()
