"""
Models package — import all ORM models so Alembic can discover them.
"""
from app.models.appointment import Appointment, AppointmentHold  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.calendar import CalendarEvent, OAuthToken  # noqa: F401
from app.models.doctor import DoctorLeave, DoctorProfile, DoctorWorkingHours  # noqa: F401
from app.models.notification import MedicationReminder, NotificationJob  # noqa: F401
from app.models.prescription import Prescription, PrescriptionItem  # noqa: F401
from app.models.user import Role, User  # noqa: F401

__all__ = [
    "User", "Role",
    "DoctorProfile", "DoctorWorkingHours", "DoctorLeave",
    "Appointment", "AppointmentHold",
    "Prescription", "PrescriptionItem",
    "NotificationJob", "MedicationReminder",
    "CalendarEvent", "OAuthToken",
    "AuditLog",
]
