import uuid
from datetime import date, datetime, timedelta, time
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.doctor import DoctorProfile, DoctorWorkingHours, DoctorLeave
from app.models.appointment import Appointment, AppointmentHold, AppointmentStatus, HoldStatus
from app.models.user import User


class DoctorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_doctors(self) -> Sequence[DoctorProfile]:
        """Fetch all active doctors with their user profiles and working hours."""
        stmt = (
            select(DoctorProfile)
            .join(User)
            .where(User.is_active.is_(True))
            .options(
                selectinload(DoctorProfile.user),
                selectinload(DoctorProfile.working_hours)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_availability(
        self, doctor_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[dict]:
        """
        Calculate available 30-min slots for a doctor over a date range.
        Takes into account working hours, leaves, active holds, and confirmed appointments.
        """
        # Fetch doctor to get timezone & slot duration
        stmt = select(DoctorProfile).options(
            selectinload(DoctorProfile.working_hours),
            selectinload(DoctorProfile.leaves).where(
                DoctorLeave.leave_date >= start_date,
                DoctorLeave.leave_date <= end_date
            )
        ).where(DoctorProfile.id == doctor_id)
        
        result = await self.db.execute(stmt)
        doctor = result.scalar_one_or_none()
        if not doctor:
            return []

        leaves_set = {leave.leave_date for leave in doctor.leaves}
        
        # Working hours mapped by day_of_week
        working_hours_map = {
            wh.day_of_week: wh 
            for wh in doctor.working_hours if wh.is_working
        }

        from datetime import timezone
        # Fetch appointments and holds within the date range
        # Converting dates to aware datetimes for boundary queries
        range_start = datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)
        range_end = datetime.combine(end_date, time.max).replace(tzinfo=timezone.utc)
        
        from sqlalchemy import or_, and_
        
        # Active holds
        holds_stmt = select(AppointmentHold).where(
            AppointmentHold.doctor_id == doctor_id,
            AppointmentHold.status == HoldStatus.HELD,
            AppointmentHold.expires_at > datetime.now(timezone.utc),
            AppointmentHold.start_time >= range_start,
            AppointmentHold.start_time <= range_end
        )
        holds_res = await self.db.execute(holds_stmt)
        active_holds = holds_res.scalars().all()
        
        # Confirmed appointments
        appts_stmt = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.start_time >= range_start,
            Appointment.start_time <= range_end
        )
        appts_res = await self.db.execute(appts_stmt)
        confirmed_appts = appts_res.scalars().all()

        availability = []
        current_date = start_date
        
        while current_date <= end_date:
            day_data = {
                "date": current_date,
                "slots": []
            }
            
            if current_date in leaves_set:
                # Doctor is on leave
                availability.append(day_data)
                current_date += timedelta(days=1)
                continue
                
            wh = working_hours_map.get(current_date.weekday())
            if not wh:
                # Not a working day
                availability.append(day_data)
                current_date += timedelta(days=1)
                continue

            # Generate slots
            slot_duration = timedelta(minutes=doctor.slot_duration_minutes)
            
            # Use aware datetimes for logic
            slot_start = datetime.combine(current_date, wh.start_time).replace(tzinfo=timezone.utc)
            slot_end = slot_start + slot_duration
            day_end = datetime.combine(current_date, wh.end_time).replace(tzinfo=timezone.utc)
            
            while slot_end <= day_end:
                status = "AVAILABLE"
                
                # Check holds (overlapping)
                for hold in active_holds:
                    if hold.start_time < slot_end and hold.end_time > slot_start:
                        status = "HELD"
                        break
                        
                # Check appointments (overlapping)
                if status == "AVAILABLE":
                    for appt in confirmed_appts:
                        if appt.start_time < slot_end and appt.end_time > slot_start:
                            status = "BOOKED"
                            break

                day_data["slots"].append({
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "status": status
                })
                
                slot_start = slot_end
                slot_end = slot_start + slot_duration

            availability.append(day_data)
            current_date += timedelta(days=1)

        return availability
