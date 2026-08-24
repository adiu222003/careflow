# Database Documentation

## Entity-Relationship Diagram

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        string phone
        enum role
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }

    doctor_profiles {
        uuid id PK
        uuid user_id FK
        string specialisation
        text bio
        numeric consultation_fee
        int slot_duration_minutes
        string timezone
    }

    doctor_working_hours {
        uuid id PK
        uuid doctor_id FK
        int day_of_week
        time start_time
        time end_time
        bool is_working
    }

    doctor_leaves {
        uuid id PK
        uuid doctor_id FK
        date leave_date
        string reason
        timestamptz created_at
    }

    appointment_holds {
        uuid id PK
        uuid doctor_id FK
        uuid patient_id FK
        timestamptz start_time
        timestamptz end_time
        timestamptz expires_at
        enum status
        timestamptz created_at
    }

    appointments {
        uuid id PK
        uuid doctor_id FK
        uuid patient_id FK
        string booking_reference UK
        timestamptz start_time
        timestamptz end_time
        enum status
        text symptoms
        text pre_visit_summary
        enum urgency_level
        enum pre_visit_ai_status
        text doctor_notes
        text post_visit_summary
        enum post_visit_ai_status
        string cancellation_reason
        timestamptz cancelled_at
    }

    prescriptions {
        uuid id PK
        uuid appointment_id FK
        uuid doctor_id FK
        uuid patient_id FK
        text notes
        timestamptz created_at
    }

    prescription_items {
        uuid id PK
        uuid prescription_id FK
        string medicine_name
        string dosage
        string frequency
        int duration_days
        text instructions
    }

    medication_reminders {
        uuid id PK
        uuid prescription_item_id FK
        uuid patient_id FK
        timestamptz scheduled_at
        enum status
        int attempts
        text last_error
    }

    notification_jobs {
        uuid id PK
        enum type
        string recipient
        uuid appointment_id FK
        jsonb payload
        timestamptz scheduled_at
        int attempts
        timestamptz next_attempt_at
        enum status
        text last_error
        timestamptz created_at
    }

    calendar_events {
        uuid id PK
        uuid appointment_id FK
        uuid user_id FK
        string google_event_id
        string calendar_id
        enum status
        enum operation
        string idempotency_key UK
        timestamptz last_synced_at
    }

    oauth_tokens {
        uuid id PK
        uuid user_id FK
        string provider
        string encrypted_access_token
        string encrypted_refresh_token
        timestamptz expires_at
        string scope
    }

    audit_logs {
        uuid id PK
        uuid actor_user_id FK
        string action
        string entity_type
        uuid entity_id
        jsonb metadata
        timestamptz created_at
    }

    users ||--o| doctor_profiles : "has"
    users ||--o{ oauth_tokens : "has"
    users ||--o{ audit_logs : "actor"
    doctor_profiles ||--o{ doctor_working_hours : "defines"
    doctor_profiles ||--o{ doctor_leaves : "takes"
    doctor_profiles ||--o{ appointments : "receives"
    doctor_profiles ||--o{ appointment_holds : "reserved for"
    users ||--o{ appointments : "books"
    users ||--o{ appointment_holds : "holds"
    appointments ||--o| prescriptions : "has"
    appointments ||--o{ notification_jobs : "triggers"
    appointments ||--o{ calendar_events : "syncs"
    prescriptions ||--o{ prescription_items : "contains"
    prescription_items ||--o{ medication_reminders : "schedules"
    users ||--o{ calendar_events : "owns"
```

## Key Relationships

| Relationship | Cardinality | Notes |
|---|---|---|
| User → DoctorProfile | 1:0..1 | Only DOCTOR users have a profile |
| DoctorProfile → Appointments | 1:many | Via doctor_id |
| User → Appointments | 1:many | Patient bookings via patient_id |
| Appointment → Prescription | 1:0..1 | One prescription per appointment |
| Prescription → PrescriptionItems | 1:many | Medication line items |
| PrescriptionItem → MedicationReminders | 1:many | One reminder per dose |
| Appointment → NotificationJobs | 1:many | Outbox jobs |
| Appointment → CalendarEvents | 1:many | One per user (patient + doctor) |

## Critical Constraints

### Appointment hold exclusion
```sql
EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
)
WHERE (status = 'HELD')
```
Prevents two HELD holds for the same doctor + overlapping time.

### Appointment exclusion (the critical one)
```sql
EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
)
WHERE (status = 'CONFIRMED')
```
Database-level final authority against double-bookings.

### Medication reminder idempotency
```sql
UNIQUE (prescription_item_id, scheduled_at)
```
Prevents duplicate reminder jobs for the same dose.

### Calendar event idempotency
```sql
UNIQUE (idempotency_key)
-- idempotency_key = sha256(appointment_id + user_id + operation)
```
Prevents duplicate calendar operations on retry.
