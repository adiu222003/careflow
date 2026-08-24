"""
Auth API endpoints: register, login, /me.
Rate-limited to prevent brute-force attacks.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import DBSession
from app.core.dependencies import CurrentUser
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.schemas.common import success
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])

_settings = get_settings()


@router.post("/register", response_model=dict, status_code=201)
async def register(request: RegisterRequest, db: DBSession) -> dict:
    """
    Register a new patient or doctor account.
    ADMIN accounts cannot be self-registered.
    """
    service = AuthService(db)
    user, token = await service.register(request)
    return success({
        "token": {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": _settings.jwt_expire_minutes * 60,
        },
        "user": UserResponse.model_validate(user).model_dump(),
    })


@router.post("/login", response_model=dict)
async def login(request: LoginRequest, db: DBSession) -> dict:
    """Authenticate and receive a JWT access token."""
    service = AuthService(db)
    user, token = await service.login(request)
    return success({
        "token": {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": _settings.jwt_expire_minutes * 60,
        },
        "user": UserResponse.model_validate(user).model_dump(),
    })


@router.get("/me", response_model=dict)
async def get_me(current_user: CurrentUser) -> dict:
    """Return the authenticated user's profile."""
    return success(UserResponse.model_validate(current_user).model_dump())
