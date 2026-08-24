import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models.appointment import Appointment, AppointmentHold


@pytest.mark.asyncio
async def test_concurrency_holds(
    concurrent_client: AsyncClient,
    seed_data: dict,
    test_engine: AsyncEngine,
) -> None:
    """
    Test A: 10 simultaneous POST /appointments/hold for the same doctor + slot.
    Result: Exactly 1 HELD hold, 9 receive 409 SLOT_NO_LONGER_AVAILABLE.
    """
    patient_token = seed_data["patient_token"]
    doctor_id = seed_data["doctor_id"]

    # Target slot
    now = datetime.now(UTC)
    start_time = now + timedelta(days=1)
    end_time = start_time + timedelta(minutes=30)

    payload = {
        "doctor_id": str(doctor_id),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }

    headers = {"Authorization": f"Bearer {patient_token}"}

    # Fire 10 concurrent requests
    tasks = [
        concurrent_client.post("/api/v1/appointments/hold", json=payload, headers=headers)
        for _ in range(10)
    ]

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    from httpx import Response
    responses: list[Response] = [r for r in raw if isinstance(r, Response)]

    # Exactly one should succeed (201), the rest should fail (409)
    successes = [r for r in responses if r.status_code == 201]
    conflicts = [r for r in responses if r.status_code == 409]

    assert len(successes) == 1
    assert len(conflicts) == 9

    # Check DB state using the fixture-provided engine (bound to THIS test's event loop)
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as db:
        stmt = select(AppointmentHold).where(
            AppointmentHold.doctor_id == doctor_id,
            AppointmentHold.start_time == start_time
        )
        holds = (await db.execute(stmt)).scalars().all()
        assert len(holds) == 1
        assert holds[0].status.value == "HELD"


@pytest.mark.asyncio
async def test_concurrency_bookings(
    concurrent_client: AsyncClient,
    seed_data: dict,
    test_engine: AsyncEngine,
) -> None:
    """
    Test B: Multiple simultaneous POST /appointments/book for the same slot.
    Result: Exactly 1 CONFIRMED appointment, others receive 409.
    """
    patient_token = seed_data["patient_token"]
    doctor_id = seed_data["doctor_id"]

    now = datetime.now(UTC)
    start_time = now + timedelta(days=2)
    end_time = start_time + timedelta(minutes=30)

    # 1. Get a single valid hold first
    hold_payload = {
        "doctor_id": str(doctor_id),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }
    headers = {"Authorization": f"Bearer {patient_token}"}
    r = await concurrent_client.post("/api/v1/appointments/hold", json=hold_payload, headers=headers)
    assert r.status_code == 201
    hold_id = r.json()["data"]["hold_id"]

    # 2. Fire 10 concurrent book requests for that same hold
    book_payload = {
        "hold_id": hold_id,
        "symptoms": "Test double click booking"
    }

    tasks = [
        concurrent_client.post("/api/v1/appointments/book", json=book_payload, headers=headers)
        for _ in range(10)
    ]

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    from httpx import Response
    responses: list[Response] = [r for r in raw if isinstance(r, Response)]

    successes = [r for r in responses if r.status_code == 201]
    conflicts = [r for r in responses if r.status_code == 409]

    assert len(successes) == 1, f"Expected 1 success, got {len(successes)}: {[r.json() for r in responses]}"
    assert len(conflicts) == 9

    # Verify DB state using the fixture-provided engine (same event loop as this test)
    from sqlalchemy.ext.asyncio import async_sessionmaker
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as db:
        stmt = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.start_time == start_time
        )
        appts = (await db.execute(stmt)).scalars().all()
        assert len(appts) == 1
        assert appts[0].status.value == "CONFIRMED"
