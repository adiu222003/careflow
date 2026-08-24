"""
API v1 router — includes all sub-routers.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import appointments, auth, doctors, health, internal

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(internal.router)
router.include_router(doctors.router)
router.include_router(appointments.router)
from app.api.v1 import calendar

router.include_router(calendar.router)

# Additional routers added in subsequent stages:
# from app.api.v1 import doctors, appointments, symptoms, consultation,
#                         prescriptions, calendar, admin
