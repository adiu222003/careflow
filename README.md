# CareFlow — Healthcare Appointment & Follow-up Manager

> Smart scheduling, AI-assisted visit summaries, and reliable patient follow-up.

[![CI](https://github.com/USERNAME/careflow/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/careflow/actions/workflows/ci.yml)

---

## Live Demo

| Service | URL |
|---|---|
| Frontend | [https://careflow.vercel.app](https://careflow.vercel.app) *(update after deployment)* |
| API Docs | [https://api.careflow.render.com/docs](https://api.careflow.render.com/docs) |

**Demo credentials** (read-only demo environment):

| Role | Email | Password |
|---|---|---|
| Patient | patient@careflow.demo | Patient@careflow123 |
| Doctor | doctor@careflow.demo | Doctor@careflow123 |
| Admin | admin@careflow.demo | Admin@careflow123 |

> ⚠️ **Free-tier cold start**: The backend is hosted on Render's free plan and may take ~30 seconds to respond after a period of inactivity. This is a known free-tier limitation.

---

## Overview

CareFlow is a full-stack healthcare scheduling platform designed around three reliability principles:

1. **The database is the authority for appointment conflicts.** PostgreSQL exclusion constraints (not application-level checks) are the final guard against double-bookings.
2. **External integrations never determine whether a core appointment transaction succeeds.** Email, Google Calendar, and AI summary failures are isolated from the booking transaction.
3. **Asynchronous notifications and calendar synchronization use retryable outbox jobs.**

### What it does

- **Patient portal**: Search doctors by specialisation, view real-time availability, book appointments, complete pre-visit symptom forms, receive AI-assisted visit summaries, view prescriptions and medication reminders.
- **Doctor portal**: View today's appointments with AI pre-visit summaries and urgency badges, submit clinical notes and prescriptions, trigger AI patient-friendly post-visit summaries.
- **Admin portal**: Manage doctors, working hours, doctor leaves (with automatic conflict resolution), view notification job status.

---

## Features

- ✅ Patient / Doctor / Admin role-based portals
- ✅ Doctor search by specialisation
- ✅ Real-time availability with slot duration per doctor
- ✅ **Concurrency-safe slot hold** (5-minute reservation with server-side expiry)
- ✅ **PostgreSQL exclusion constraints** — database-level double-booking prevention
- ✅ Pre-visit symptom form → AI summary (urgency: Low/Medium/High)
- ✅ Doctor consultation notes → AI patient-friendly post-visit summary
- ✅ Prescription + medication reminder scheduling
- ✅ **Outbox-pattern email notifications** (appointment confirmation, reminders, cancellation)
- ✅ **Google Calendar OAuth 2.0** integration with idempotent event management
- ✅ Doctor leave management with automatic appointment cancellation
- ✅ Cancellation and rescheduling
- ✅ **Graceful degradation** — app works fully without LLM, email, or Calendar
- ✅ Audit log for all important business actions
- ✅ GitHub Actions scheduler for background jobs on free hosting

---

## Architecture

```
┌───────────────────┐
│   Next.js 15      │  Patient / Doctor / Admin portals
│   TypeScript      │  Tailwind CSS + shadcn/ui
└─────────┬─────────┘
          │ HTTPS / REST
┌─────────▼─────────┐
│   FastAPI         │  Python 3.13
│                   │
│   Auth / RBAC     │  JWT + argon2-cffi
│   Booking Engine  │  Concurrency-safe slots + holds
│   AI Service      │  Gemini (with fallback)
│   Notification    │  Outbox pattern + Resend
│   Calendar Service│  Google Calendar OAuth 2.0
└─────────┬─────────┘
          │
┌─────────▼─────────┐
│   PostgreSQL      │  Supabase (hosted)
│                   │
│   Exclusion constraints (btree_gist)
│   Outbox job queue
│   Encrypted OAuth tokens
└────────────────────┘
```

### Concurrency Safety

Appointment availability is enforced server-side. Slot holds and confirmed appointments are protected using PostgreSQL transactions and database-level conflict constraints. Concurrent booking attempts cannot create overlapping appointments for the same doctor and time range; conflicting requests receive a controlled 409 SLOT_NO_LONGER_AVAILABLE response.

```sql
-- No two CONFIRMED appointments for same doctor + overlapping time
ALTER TABLE appointments
ADD CONSTRAINT no_overlapping_confirmed_appointments
EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(start_time, end_time, '[)') WITH &&
)
WHERE (status = 'CONFIRMED');
```

If two requests pass application-level checks simultaneously, the database constraint rejects the second one. The application catches the constraint violation and returns `SLOT_NO_LONGER_AVAILABLE`.

### AI Safety & Reliability

CareFlow uses Gemini only for documentation assistance. It does not make diagnoses, prescribe medications, or determine clinical decisions. AI output is schema-validated before storage, and failures fall back to deterministic content without affecting appointment transactions. AI generation is asynchronous and non-critical; failure leaves the appointment valid and allows explicit regeneration.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI, Python 3.13, SQLAlchemy 2, Pydantic v2 |
| Database | PostgreSQL (Supabase) |
| Auth | JWT (PyJWT), argon2-cffi |
| AI | Google Gemini API |
| Email | Resend |
| Calendar | Google Calendar API (OAuth 2.0) |
| Scheduler | GitHub Actions (cron every 5 min) |
| Frontend hosting | Vercel |
| Backend hosting | Render (free tier) |

---

## Repository Structure

```
careflow/
├── .github/workflows/
│   ├── ci.yml              # lint + test + build
│   └── scheduler.yml       # process background jobs
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # config, database, security, dependencies
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── api/v1/         # Route handlers
│   │   ├── services/       # Business logic
│   │   └── workers/        # Background job processor
│   ├── alembic/            # DB migrations
│   ├── tests/
│   ├── scripts/seed.py
│   └── requirements.txt
├── frontend/
│   ├── app/                # Next.js App Router
│   ├── components/
│   ├── lib/                # API client, auth utilities
│   └── types/
├── docs/
│   ├── system-design.md    # ≤800 words
│   ├── database.md         # ER diagram
│   ├── api.md
│   ├── llm-prompts.md
│   ├── deployment.md
│   └── google-calendar.md
├── .env.example
├── docker-compose.yml
└── render.yaml
```

---

## Local Setup

### Prerequisites
- Python 3.13+
- Node.js 22+
- PostgreSQL 16+ (or Docker)

### 1. Clone and configure

```bash
git clone https://github.com/USERNAME/careflow.git
cd careflow
cp .env.example .env
# Edit .env with your local credentials
```

### 2. Start database (Docker)

```bash
docker compose up postgres -d
```

### 3. Backend

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
```

Backend available at: http://localhost:8000  
API docs: http://localhost:8000/docs

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: http://localhost:3000

### 5. Run tests

```bash
cd backend
pytest tests/ -v --cov=app
```

---

## Environment Variables

See [`.env.example`](.env.example) for all required variables with descriptions.

Key flags:

| Variable | Default | Effect when false |
|---|---|---|
| `ENABLE_LLM` | true | Deterministic fallback summary used |
| `ENABLE_EMAIL` | true | Notifications logged only |
| `ENABLE_GOOGLE_CALENDAR` | true | Calendar sync unavailable |

---

## Security Notes

- Passwords hashed with argon2-cffi (OWASP recommended)
- JWTs signed with HS256; role always verified against DB, never trusted from frontend
- Google OAuth refresh tokens encrypted at rest with Fernet
- CORS restricted to `CORS_ORIGINS` environment variable
- No medical content in Google Calendar event descriptions
- No secrets in logs

> This is a **security-conscious healthcare application prototype**. It is not claimed to be HIPAA-compliant.

---

## Deployment

See [`docs/deployment.md`](docs/deployment.md) for full deployment instructions for Vercel (frontend), Render (backend), and Supabase (database).

---

## Known Free-Tier Limitations

| Service | Limitation |
|---|---|
| Render | ~30s cold start after 15 min inactivity |
| Supabase | 500 MB database storage |
| Resend | 100 emails/day, 3,000/month |
| GitHub Actions scheduler | ~5 min job processing delay (not exact-time) |

---

## Documentation

- [System Design](docs/system-design.md) — concurrency, outbox pattern, slot holds, leave conflicts
- [Database](docs/database.md) — ER diagram and schema
- [API Reference](docs/api.md) — all endpoints
- [LLM Prompts](docs/llm-prompts.md) — pre-visit and post-visit prompt design
- [Google Calendar Setup](docs/google-calendar.md) — OAuth configuration
- [Deployment](docs/deployment.md) — Vercel + Render + Supabase
- [Test Cases](docs/test-cases.md) — 22 acceptance tests

---

*Submission deadline: [SUBMISSION_DEADLINE] — replace with actual date before pushing.*
