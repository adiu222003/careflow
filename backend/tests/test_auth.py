import uuid

import pytest
from httpx import AsyncClient


def get_patient_data():
    return {
        "email": f"patient_{uuid.uuid4().hex[:8]}@careflow.com",
        "password": "securepassword123",
        "full_name": "Test Patient",
        "phone": "+1234567890",
        "role": "PATIENT",
    }

def get_doctor_data():
    return {
        "email": f"doctor_{uuid.uuid4().hex[:8]}@careflow.com",
        "password": "securepassword123",
        "full_name": "Dr. Test Doctor",
        "phone": "+1987654321",
        "role": "DOCTOR",
    }

@pytest.mark.asyncio
async def test_register_patient(client: AsyncClient) -> None:
    pd = get_patient_data()
    response = await client.post("/api/v1/auth/register", json=pd)
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert "token" in data["data"]
    assert "user" in data["data"]
    assert data["data"]["user"]["email"] == pd["email"]
    assert data["data"]["user"]["role"] == "PATIENT"
    # password must never be returned
    assert "password" not in data["data"]["user"]
    assert "password_hash" not in data["data"]["user"]

@pytest.mark.asyncio
async def test_register_doctor(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=get_doctor_data())
    assert response.status_code == 201
    assert response.json()["data"]["user"]["role"] == "DOCTOR"

@pytest.mark.asyncio
async def test_register_admin_blocked(client: AsyncClient) -> None:
    """ADMIN accounts must not be self-registerable."""
    data = {**get_patient_data(), "email": f"admin_{uuid.uuid4().hex[:8]}@careflow.com", "role": "ADMIN"}
    response = await client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert response.json()["success"] is False

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    pd = get_patient_data()
    await client.post("/api/v1/auth/register", json=pd)
    response = await client.post("/api/v1/auth/register", json=pd)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    pd = get_patient_data()
    await client.post("/api/v1/auth/register", json=pd)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": pd["email"], "password": pd["password"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["token"]["access_token"]
    assert data["data"]["token"]["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    pd = get_patient_data()
    await client.post("/api/v1/auth/register", json=pd)
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": pd["email"], "password": "wrongpassword"},
    )
    assert response.status_code == 422
    assert "password" in response.json()["error"]["message"].lower() or \
           "invalid" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@careflow.com", "password": "anypassword"},
    )
    assert response.status_code == 422
    assert "invalid" in response.json()["error"]["message"].lower()

@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient) -> None:
    pd = get_patient_data()
    reg = await client.post("/api/v1/auth/register", json=pd)
    token = reg.json()["data"]["token"]["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["email"] == pd["email"]

@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer totally.invalid.token"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"

@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient) -> None:
    data = {**get_patient_data(), "email": f"new_{uuid.uuid4().hex[:8]}@careflow.com", "password": "short"}
    response = await client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
