"""
User ORM model — shared across all three portals (Patient / Doctor / Admin).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.audit import AuditLog
    from app.models.calendar import OAuthToken
    from app.models.doctor import DoctorProfile


import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Role(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    doctor_profile: Mapped[DoctorProfile | None] = relationship(  # noqa: F821
        "DoctorProfile", back_populates="user", uselist=False, lazy="selectin"
    )
    oauth_tokens: Mapped[list[OAuthToken]] = relationship(  # noqa: F821
        "OAuthToken", back_populates="user", lazy="dynamic"
    )
    audit_logs_as_actor: Mapped[list[AuditLog]] = relationship(  # noqa: F821
        "AuditLog", back_populates="actor", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
