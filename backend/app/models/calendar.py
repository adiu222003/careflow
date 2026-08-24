"""
Google Calendar event and OAuth token ORM models.

Calendar events use idempotency to prevent duplicate events on retry:
  - google_event_id is persisted after first successful creation
  - On retry: if google_event_id already set → skip creation
  - On delete retry: if Google returns 404 → already deleted → mark CANCELLED
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.user import User


import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CalendarEventStatus(str, enum.Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CalendarOperation(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class CalendarEvent(Base):
    """
    Google Calendar sync state for each appointment/user pair.
    Stores the google_event_id for idempotent retries.
    """
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CalendarEventStatus] = mapped_column(
        Enum(CalendarEventStatus),
        nullable=False,
        default=CalendarEventStatus.PENDING,
        index=True,
    )
    operation: Mapped[CalendarOperation] = mapped_column(
        Enum(CalendarOperation), nullable=False, default=CalendarOperation.CREATE
    )
    # sha256(appointment_id + user_id + operation) — prevents duplicate ops
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    appointment: Mapped[Appointment] = relationship(  # noqa: F821
        "Appointment", back_populates="calendar_events"
    )
    user: Mapped[User] = relationship("User")  # noqa: F821


class OAuthToken(Base):
    """
    Encrypted Google OAuth refresh tokens.
    Access token and refresh token are Fernet-encrypted at rest.
    Never expose these values to the frontend.
    """
    __tablename__ = "oauth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="google")
    encrypted_access_token: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="oauth_tokens")  # noqa: F821
