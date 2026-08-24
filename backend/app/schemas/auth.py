"""
Auth request/response Pydantic schemas.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    role: Role = Role.PATIENT

    @field_validator("role")
    @classmethod
    def restrict_admin_self_registration(cls, v: Role) -> Role:
        """
        ADMIN accounts must be created by seeding or an existing admin —
        never by self-registration.
        """
        if v == Role.ADMIN:
            raise ValueError("ADMIN role cannot be self-registered.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: Role
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: TokenResponse
    user: UserResponse
