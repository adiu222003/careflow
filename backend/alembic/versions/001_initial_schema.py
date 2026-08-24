"""Initial schema — all tables, indexes, and concurrency constraints.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-08-24 UTC

Key design decisions:
  - btree_gist extension enables range exclusion constraints
  - appointment_holds: exclusion on HELD rows prevents duplicate holds
  - appointments: exclusion on CONFIRMED rows is the final DB-level booking guard
  - medication_reminders: unique (prescription_item_id, scheduled_at) = idempotency key
  - calendar_events: unique idempotency_key prevents duplicate calendar operations
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable btree_gist for exclusion constraints ──────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "role",
            sa.Enum("PATIENT", "DOCTOR", "ADMIN", name="role"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # ── doctor_profiles ──────────────────────────────────────────────────────
    op.create_table(
        "doctor_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("specialisation", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("consultation_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_doctor_profiles_user_id"),
    )
    op.create_index("ix_doctor_profiles_specialisation", "doctor_profiles", ["specialisation"])

    # ── doctor_working_hours ─────────────────────────────────────────────────
    op.create_table(
        "doctor_working_hours",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_working", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_doctor_working_hours_doctor_id", "doctor_working_hours", ["doctor_id"])

    # ── doctor_leaves ────────────────────────────────────────────────────────
    op.create_table(
        "doctor_leaves",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_doctor_leaves_doctor_date", "doctor_leaves", ["doctor_id", "leave_date"])

    # ── appointment_holds ────────────────────────────────────────────────────
    op.create_table(
        "appointment_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("HELD", "EXPIRED", "CONVERTED", name="holdstatus"),
            nullable=False,
            server_default="HELD",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_appointment_holds_doctor_id", "appointment_holds", ["doctor_id"])
    op.create_index("ix_appointment_holds_patient_id", "appointment_holds", ["patient_id"])
    op.create_index("ix_appointment_holds_expires_status", "appointment_holds", ["expires_at", "status"])

    # DB-level exclusion: no two HELD holds for same doctor + overlapping time range
    op.execute("""
        ALTER TABLE appointment_holds
        ADD CONSTRAINT no_overlapping_active_holds
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        )
        WHERE (status = 'HELD')
    """)

    # ── appointments ─────────────────────────────────────────────────────────
    op.create_table(
        "appointments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("booking_reference", sa.String(20), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("CONFIRMED", "COMPLETED", "CANCELLED", name="appointmentstatus"),
            nullable=False,
            server_default="CONFIRMED",
        ),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("pre_visit_summary", sa.Text(), nullable=True),
        sa.Column(
            "urgency_level",
            sa.Enum("Low", "Medium", "High", name="urgencylevel"),
            nullable=True,
        ),
        sa.Column(
            "pre_visit_ai_status",
            sa.Enum("PENDING", "SUCCESS", "FAILED", name="aistatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("doctor_notes", sa.Text(), nullable=True),
        sa.Column("post_visit_summary", sa.Text(), nullable=True),
        sa.Column(
            "post_visit_ai_status",
            sa.Enum("PENDING", "SUCCESS", "FAILED", name="aistatus", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_appointments_doctor_id", "appointments", ["doctor_id"])
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index("ix_appointments_start_time", "appointments", ["start_time"])
    op.create_index("ix_appointments_booking_reference", "appointments", ["booking_reference"], unique=True)

    # THE CRITICAL CONSTRAINT: no two CONFIRMED appointments for same doctor + overlapping time
    # This is the database-level final authority for concurrency safety.
    op.execute("""
        ALTER TABLE appointments
        ADD CONSTRAINT no_overlapping_confirmed_appointments
        EXCLUDE USING gist (
            doctor_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        )
        WHERE (status = 'CONFIRMED')
    """)

    # ── prescriptions ─────────────────────────────────────────────────────────
    op.create_table(
        "prescriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("doctor_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("appointment_id", name="uq_prescriptions_appointment_id"),
    )
    op.create_index("ix_prescriptions_appointment_id", "prescriptions", ["appointment_id"])
    op.create_index("ix_prescriptions_patient_id", "prescriptions", ["patient_id"])

    # ── prescription_items ────────────────────────────────────────────────────
    op.create_table(
        "prescription_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prescription_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medicine_name", sa.String(255), nullable=False),
        sa.Column("dosage", sa.String(100), nullable=False),
        sa.Column("frequency", sa.String(100), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
    )
    op.create_index("ix_prescription_items_prescription_id", "prescription_items", ["prescription_id"])

    # ── medication_reminders ──────────────────────────────────────────────────
    op.create_table(
        "medication_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("prescription_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prescription_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "SENT", "FAILED", "CANCELLED", name="reminderstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        # Idempotency: same prescription item + time cannot create two reminders
        sa.UniqueConstraint("prescription_item_id", "scheduled_at", name="uq_reminder_idempotency"),
    )
    op.create_index("ix_medication_reminders_scheduled", "medication_reminders", ["scheduled_at", "status"])
    op.create_index("ix_medication_reminders_patient_id", "medication_reminders", ["patient_id"])

    # ── notification_jobs ─────────────────────────────────────────────────────
    op.create_table(
        "notification_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "type",
            sa.Enum(
                "APPOINTMENT_CONFIRMATION_PATIENT",
                "APPOINTMENT_CONFIRMATION_DOCTOR",
                "APPOINTMENT_REMINDER_PATIENT",
                "APPOINTMENT_REMINDER_DOCTOR",
                "APPOINTMENT_CANCELLATION_PATIENT",
                "APPOINTMENT_CANCELLATION_DOCTOR",
                "DOCTOR_LEAVE_CANCELLATION",
                "POST_VISIT_SUMMARY",
                "MEDICATION_REMINDER",
                name="notificationjobtype",
            ),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "status",
            sa.Enum("PENDING", "PROCESSING", "SENT", "FAILED", name="notificationjobstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_jobs_status_next", "notification_jobs", ["status", "next_attempt_at"])
    op.create_index("ix_notification_jobs_appointment_id", "notification_jobs", ["appointment_id"])

    # ── calendar_events ────────────────────────────────────────────────────────
    op.create_table(
        "calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("appointment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("google_event_id", sa.String(255), nullable=True),
        sa.Column("calendar_id", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "SYNCED", "FAILED", "CANCELLED", name="calendareventstatus"),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "operation",
            sa.Enum("CREATE", "UPDATE", "DELETE", name="calendaroperation"),
            nullable=False,
            server_default="CREATE",
        ),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_calendar_events_idempotency_key"),
    )
    op.create_index("ix_calendar_events_appointment_id", "calendar_events", ["appointment_id"])
    op.create_index("ix_calendar_events_user_id", "calendar_events", ["user_id"])
    op.create_index("ix_calendar_events_status", "calendar_events", ["status"])

    # ── oauth_tokens ───────────────────────────────────────────────────────────
    op.create_table(
        "oauth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False, server_default="google"),
        sa.Column("encrypted_access_token", sa.String(4096), nullable=True),
        sa.Column("encrypted_refresh_token", sa.String(4096), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scope", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_oauth_tokens_user_id", "oauth_tokens", ["user_id"])

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_actor", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("oauth_tokens")
    op.drop_table("calendar_events")
    op.drop_table("notification_jobs")
    op.drop_table("medication_reminders")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
    op.drop_table("appointments")
    op.drop_table("appointment_holds")
    op.drop_table("doctor_leaves")
    op.drop_table("doctor_working_hours")
    op.drop_table("doctor_profiles")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS notificationjobstatus")
    op.execute("DROP TYPE IF EXISTS notificationjobtype")
    op.execute("DROP TYPE IF EXISTS reminderstatus")
    op.execute("DROP TYPE IF EXISTS calendareventstatus")
    op.execute("DROP TYPE IF EXISTS calendaroperation")
    op.execute("DROP TYPE IF EXISTS aistatus")
    op.execute("DROP TYPE IF EXISTS urgencylevel")
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.execute("DROP TYPE IF EXISTS holdstatus")
    op.execute("DROP TYPE IF EXISTS role")
