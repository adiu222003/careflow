"""
Pytest configuration and fixtures for the CareFlow test suite.
Uses a separate test database; runs migrations before each test session.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Set test environment variables before importing app ──────────────────────
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/careflow_test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-16-chars")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "")
os.environ.setdefault("ENABLE_LLM", "false")
os.environ.setdefault("ENABLE_EMAIL", "false")
os.environ.setdefault("ENABLE_GOOGLE_CALENDAR", "false")
os.environ.setdefault("INTERNAL_JOB_SECRET", "test-job-secret")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("BACKEND_URL", "http://localhost:8000")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_engine():
    from sqlalchemy import text
    from sqlalchemy.pool import NullPool
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession]:
    """Yields a fresh session per test, rolled back on completion."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """AsyncClient with the test DB session injected."""
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
@pytest_asyncio.fixture
async def concurrent_client(test_engine) -> AsyncGenerator[AsyncClient]:
    """AsyncClient that overrides get_db to yield a fresh session from test_engine per request."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
import uuid

from app.core.security import create_access_token, hash_password
from app.models.doctor import DoctorProfile
from app.models.user import Role, User


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession) -> dict:
    """Creates a basic patient and doctor for tests."""
    unique_suffix = str(uuid.uuid4())[:8]
    patient_id = uuid.uuid4()
    doctor_user_id = uuid.uuid4()
    doctor_profile_id = uuid.uuid4()

    patient = User(
        id=patient_id,
        email=f"patient_{unique_suffix}@careflow.com",
        password_hash=hash_password("securepassword123"),
        full_name="Test Patient",
        role=Role.PATIENT,
        is_active=True
    )

    doctor_user = User(
        id=doctor_user_id,
        email=f"doctor_{unique_suffix}@careflow.com",
        password_hash=hash_password("securepassword123"),
        full_name="Dr. Test",
        role=Role.DOCTOR,
        is_active=True
    )

    doctor_profile = DoctorProfile(
        id=doctor_profile_id,
        user_id=doctor_user_id,
        specialisation="General",
        slot_duration_minutes=30
    )

    db_session.add_all([patient, doctor_user, doctor_profile])
    await db_session.commit()

    patient_token = create_access_token(str(patient_id), "PATIENT")
    doctor_token = create_access_token(str(doctor_user_id), "DOCTOR")

    return {
        "patient_id": patient_id,
        "doctor_user_id": doctor_user_id,
        "doctor_id": doctor_profile_id,
        "patient_token": patient_token,
        "doctor_token": doctor_token
    }
