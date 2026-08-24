"""
FastAPI dependencies for authentication and role-based access control.
Role is always read from the JWT — never trusted from the request body or headers.
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.database import DBSession
from app.core.security import decode_access_token
from app.models.user import Role, User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DBSession,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer)
    ] = None,
) -> User:
    """
    Validate JWT and return the authenticated User ORM object.
    Raises 401 on missing/invalid token, 404 if user no longer exists.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NOT_AUTHENTICATED", "message": "Authentication required."},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload["sub"]
        token_role: str = payload["role"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_TOKEN", "message": "Token is invalid or expired."},
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "USER_NOT_FOUND", "message": "User account not found or inactive."},
        )

    # Sanity-check: role in token must match role in DB
    if user.role.value != token_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ROLE_MISMATCH", "message": "Token role does not match account role."},
        )

    return user


def require_roles(*roles: Role):
    """
    Factory that returns a FastAPI dependency enforcing that the authenticated
    user has one of the specified roles.
    Usage: Depends(require_roles(Role.ADMIN, Role.DOCTOR))
    """
    async def _check(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": "You do not have permission to perform this action.",
                },
            )
        return current_user
    return _check


# Convenience type aliases
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
DoctorUser = Annotated[User, Depends(require_roles(Role.DOCTOR))]
PatientUser = Annotated[User, Depends(require_roles(Role.PATIENT))]
AdminOrDoctorUser = Annotated[User, Depends(require_roles(Role.ADMIN, Role.DOCTOR))]


def check_appointment_access(appointment: object, current_user: User) -> None:
    """
    Shared authorization check for appointment endpoints.
    Raises 403 if the current user is not the patient, the assigned doctor,
    or an admin.
    """
    from app.models.appointment import Appointment  # local import to avoid circular
    appt: Appointment = appointment  # type: ignore[assignment]

    if current_user.role == Role.ADMIN:
        return

    if current_user.role == Role.PATIENT:
        if appt.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied."},
            )
        return

    if current_user.role == Role.DOCTOR:
        # Doctor profile FK is doctor_id on appointment
        if not hasattr(current_user, "doctor_profile") or current_user.doctor_profile is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail={"code": "FORBIDDEN", "message": "Access denied."})
        if appt.doctor_id != current_user.doctor_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Access denied."},
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Access denied."},
    )
