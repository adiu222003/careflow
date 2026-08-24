"""
CareFlow Demo Seed Script.
Creates demo accounts and sample data for local development and assessment demonstration.

IMPORTANT: These are DEMO credentials only. Change all passwords before any real deployment.
DO NOT commit real passwords or patient data to source control.

Usage:
  cd backend
  python scripts/seed.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta

# Allow importing app from backend root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set required env vars for seeding (if not already in .env)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/careflow")
os.environ.setdefault("JWT_SECRET", "dev-jwt-secret-change-in-production")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "")
os.environ.setdefault("ENABLE_LLM", "false")
os.environ.setdefault("ENABLE_EMAIL", "false")
os.environ.setdefault("ENABLE_GOOGLE_CALENDAR", "false")
os.environ.setdefault("INTERNAL_JOB_SECRET", "dev-job-secret")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("BACKEND_URL", "http://localhost:8000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import Role, User
from app.models.doctor import DoctorProfile, DoctorWorkingHours
from sqlalchemy import select


DEMO_CREDENTIALS = """
╔══════════════════════════════════════════════════════════╗
║           CareFlow Demo Credentials                      ║
║  DEMO ONLY — Do not use in production                    ║
╠══════════════════════════════════════════════════════════╣
║  Admin:    admin@careflow.demo   / Admin@careflow123     ║
║  Doctor 1: doctor@careflow.demo  / Doctor@careflow123    ║
║  Doctor 2: sharma@careflow.demo  / Doctor@careflow123    ║
║  Doctor 3: patel@careflow.demo   / Doctor@careflow123    ║
║  Patient:  patient@careflow.demo / Patient@careflow123   ║
╚══════════════════════════════════════════════════════════╝
"""

DEMO_DOCTORS = [
    {
        "email": "doctor@careflow.demo",
        "full_name": "Dr. Ananya Sharma",
        "specialisation": "Cardiology",
        "bio": "Senior Cardiologist with 15 years of experience in interventional cardiology and heart failure management.",
        "slot_duration_minutes": 30,
        "timezone": "Asia/Kolkata",
    },
    {
        "email": "sharma@careflow.demo",
        "full_name": "Dr. Rajesh Patel",
        "specialisation": "Neurology",
        "bio": "Neurologist specialising in headache disorders, epilepsy, and stroke rehabilitation.",
        "slot_duration_minutes": 30,
        "timezone": "Asia/Kolkata",
    },
    {
        "email": "patel@careflow.demo",
        "full_name": "Dr. Priya Singh",
        "specialisation": "Dermatology",
        "bio": "Consultant Dermatologist with expertise in medical and cosmetic dermatology.",
        "slot_duration_minutes": 20,
        "timezone": "Asia/Kolkata",
    },
]

WORKING_DAYS = [0, 1, 2, 3, 4]  # Monday–Friday


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        print("Seeding CareFlow demo data...")

        # ── Admin ─────────────────────────────────────────────────────────
        existing_admin = await db.execute(select(User).where(User.email == "admin@careflow.demo"))
        if existing_admin.scalar_one_or_none() is None:
            admin = User(
                email="admin@careflow.demo",
                password_hash=hash_password("Admin@careflow123"),
                full_name="CareFlow Admin",
                role=Role.ADMIN,
            )
            db.add(admin)
            print("  [OK] Admin account created")

        # ── Patient ───────────────────────────────────────────────────────
        existing_patient = await db.execute(select(User).where(User.email == "patient@careflow.demo"))
        if existing_patient.scalar_one_or_none() is None:
            patient = User(
                email="patient@careflow.demo",
                password_hash=hash_password("Patient@careflow123"),
                full_name="Aditya Kumar",
                phone="+91 98765 43210",
                role=Role.PATIENT,
            )
            db.add(patient)
            print("  [OK] Patient account created")

        # ── Doctors ───────────────────────────────────────────────────────
        for doc_data in DEMO_DOCTORS:
            existing_doc = await db.execute(select(User).where(User.email == doc_data["email"]))
            if existing_doc.scalar_one_or_none() is None:
                doctor_user = User(
                    email=doc_data["email"],
                    password_hash=hash_password("Doctor@careflow123"),
                    full_name=doc_data["full_name"],
                    role=Role.DOCTOR,
                )
                db.add(doctor_user)
                await db.flush()  # get user.id

                doctor_profile = DoctorProfile(
                    user_id=doctor_user.id,
                    specialisation=doc_data["specialisation"],
                    bio=doc_data["bio"],
                    consultation_fee=500.00,
                    slot_duration_minutes=doc_data["slot_duration_minutes"],
                    timezone=doc_data["timezone"],
                )
                db.add(doctor_profile)
                await db.flush()  # get doctor_profile.id

                # Working hours Mon–Fri 09:00–17:00
                for day in WORKING_DAYS:
                    wh = DoctorWorkingHours(
                        doctor_id=doctor_profile.id,
                        day_of_week=day,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                        is_working=True,
                    )
                    db.add(wh)

                print(f"  [OK] Doctor created: {doc_data['full_name']} ({doc_data['specialisation']})")

        await db.commit()
        print("\nSeed complete!")
        print(DEMO_CREDENTIALS)


if __name__ == "__main__":
    asyncio.run(seed())
