from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import DBSession
from app.core.dependencies import CurrentUser
from app.schemas.common import success
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/auth/url", response_model=dict)
async def get_auth_url(
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """
    Get the Google OAuth 2.0 authorization URL.
    The user_id is passed as the OAuth state parameter.
    """
    service = CalendarService(db)
    url = service.get_authorization_url(current_user.id)
    return success({"auth_url": url})


@router.get("/auth/callback", response_model=dict)
async def auth_callback(
    db: DBSession,
    state: str = Query(...),
    code: str = Query(...),
) -> dict:
    """
    Google OAuth 2.0 callback endpoint.
    Exchanges the authorization code for tokens and stores them.
    """
    try:
        user_id = uuid.UUID(state)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_STATE", "message": "Invalid OAuth state parameter."},
        )

    service = CalendarService(db)
    try:
        await service.exchange_code_for_tokens(code, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "OAUTH_FAILED", "message": str(e)},
        )

    return success({"message": "Calendar connected successfully."})


@router.delete("/auth", response_model=dict)
async def disconnect_calendar(
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """
    Disconnects the Google Calendar by deleting the OAuth tokens.
    """
    from sqlalchemy import delete

    from app.models.calendar import OAuthToken

    stmt = delete(OAuthToken).where(OAuthToken.user_id == current_user.id)
    await db.execute(stmt)
    await db.commit()

    return success({"message": "Calendar disconnected."})
