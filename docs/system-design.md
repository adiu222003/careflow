# System Design — CareFlow

*Healthcare Appointment & Follow-up Manager*

---

## Overview

CareFlow is a modular-monolith healthcare scheduling platform. The core design centres on four reliability goals: concurrent booking safety, notification resilience, AI isolation, and calendar idempotency.

---

## 1. Double-Booking Prevention

The naive approach — "check if the slot is free, then insert" — fails under concurrency. If two requests check simultaneously, both see the slot as available, and both proceed to insert.

CareFlow uses two layers.

**Application layer** (first filter): before inserting, the service validates doctor availability, working hours, leave, and active holds within a database transaction.

**Database layer** (final authority): a PostgreSQL exclusion constraint using `btree_gist` enforces that no two `CONFIRMED` appointments can have the same `doctor_id` with overlapping `tstzrange(start_time, end_time)`.

```sql
ALTER TABLE appointments
ADD CONSTRAINT no_overlapping_confirmed_appointments
EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
)
WHERE (status = 'CONFIRMED');
```

When two concurrent requests both pass the application check, the first `INSERT` wins. The second receives a PostgreSQL constraint violation. The service catches this and returns `SLOT_NO_LONGER_AVAILABLE` to the frontend. No duplicate booking is ever created.

The same pattern protects `appointment_holds` from duplicate reservations while in `HELD` status.

---

## 2. Slot Hold Mechanism

When a patient selects a slot, the system creates a temporary hold before presenting the symptom form. This prevents the slot from being taken while the patient fills in information.

```
Patient selects slot
        ↓
BEGIN TRANSACTION
  Check for conflicts (application)
  INSERT appointment_holds (status=HELD, expires_at=now+5min)
  → DB exclusion constraint enforces uniqueness
COMMIT
        ↓
Frontend displays 5-minute countdown (display only; server is authoritative)
        ↓
Patient submits symptoms + confirms
        ↓
BEGIN TRANSACTION
  Verify hold.patient_id == current_user
  Verify hold.expires_at > now()
  Verify no doctor leave on that date
  INSERT appointments (status=CONFIRMED)
  → DB exclusion constraint fires on race condition
  UPDATE hold status=CONVERTED
  INSERT notification_jobs + calendar_events
COMMIT
```

If the hold expires before confirmation, the slot becomes available again. The backend validates `expires_at > now()` server-side — never the frontend timer.

Stale holds (status=HELD, expires_at < now()) are expired by the background job processor to status=EXPIRED.

---

## 3. Doctor Leave Conflict Handling

When an admin marks a leave date:

```
BEGIN TRANSACTION
  INSERT doctor_leaves
  SELECT CONFIRMED appointments on that date
  FOR EACH affected appointment:
    UPDATE status=CANCELLED, cancellation_reason=DOCTOR_ON_LEAVE
    INSERT notification_jobs (patient + doctor)
    INSERT calendar_events (operation=DELETE)
COMMIT
```

Appointments are never deleted. Cancellation reasons are preserved. The worker then calls Resend and Google Calendar asynchronously. If the admin removes the leave, new bookings become possible but previously cancelled appointments are not automatically restored — this is an intentional auditability decision.

---

## 4. Notification Failure Handling

All notifications use an outbox pattern. Inside the appointment transaction, the service inserts `notification_jobs` rows alongside the appointment change. External API calls happen after the commit.

```
BEGIN
  appointment row (CONFIRMED)
  notification_job (patient confirmation)
  notification_job (doctor confirmation)
  calendar_event (patient, PENDING)
  calendar_event (doctor, PENDING)
COMMIT

Worker (every ~5 min via GitHub Actions):
  SELECT jobs WHERE status=PENDING AND next_attempt_at <= now()
  FOR UPDATE SKIP LOCKED          ← safe for concurrent workers
  → call Resend
  → SUCCESS: status=SENT
  → FAILURE: increment attempts
              next_attempt_at = exponential backoff (1m, 5m, 15m)
              after 5 failures: status=FAILED_PERMANENTLY
```

A committed appointment is never rolled back because of an email failure. The job record retains the last error for admin inspection.

Medication reminders follow the same pattern. Idempotency is enforced by a unique constraint on `(prescription_item_id, scheduled_at)`.

---

## 5. Calendar Idempotency

Google Calendar API calls can fail after the server accepts the request. On retry, a duplicate event would be created. CareFlow prevents this by:

- Persisting `google_event_id` after first successful creation
- On CREATE retry: if `google_event_id` already set → skip, mark SYNCED
- On DELETE retry: if Google returns 404 → already deleted → mark CANCELLED
- Each operation has an `idempotency_key = sha256(appointment_id + user_id + operation)` with a database unique constraint

Calendar failure never blocks the appointment transaction.

---

## 6. AI Isolation

The Gemini API is called after the appointment or consultation is saved. If it fails (timeout, API error, malformed JSON, invalid urgency value), a deterministic fallback summary is stored and `ai_status` is set to `FAILED`. The doctor sees the raw patient input. A retry endpoint allows re-triggering generation.

The LLM is strictly a documentation assistant. It cannot modify appointment status, prescriptions, or any business data. All structured output is validated by Pydantic before persistence.

---

## 7. Graceful Degradation

Feature flags `ENABLE_LLM`, `ENABLE_EMAIL`, and `ENABLE_GOOGLE_CALENDAR` allow the application to run without any external API credentials. This makes local development and CI trivial, and ensures evaluators can run the application immediately.

---

*Word count: ~720*
