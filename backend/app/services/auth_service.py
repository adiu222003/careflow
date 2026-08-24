"""
Authentication service — registration, login, token creation.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register(self, data: RegisterRequest) -> tuple[User, str]:
        """
        Register a new user.
        Returns (user, access_token).
        Raises ConflictError if email already exists.
        """
        existing = await self._db.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("An account with this email address already exists.")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            phone=data.phone,
            role=data.role,
        )
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)

        token = create_access_token(str(user.id), user.role.value)
        return user, token

    async def login(self, data: LoginRequest) -> tuple[User, str]:
        """
        Authenticate a user.
        Returns (user, access_token).
        Raises ValidationError on bad credentials (generic message to avoid enumeration).
        """
        result = await self._db.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        # Constant-time comparison prevents timing attacks; same message for both
        # "user not found" and "wrong password" to prevent email enumeration.
        if user is None or not verify_password(data.password, user.password_hash):
            raise ValidationError("Invalid email or password.")

        if not user.is_active:
            raise ValidationError("This account has been deactivated.")

        token = create_access_token(str(user.id), user.role.value)
        return user, token
