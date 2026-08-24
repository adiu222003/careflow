# Deployment Guide

## Overview

| Service | Provider | Free Tier |
|---|---|---|
| Frontend | Vercel | Yes — unlimited hobby |
| Backend | Render | Yes — spins down after 15 min inactivity |
| Database | Supabase | Yes — 500 MB PostgreSQL |
| Email | Resend | Yes — 3,000/month, 100/day |
| AI | Gemini API | Yes — free developer tier |
| Scheduler | GitHub Actions | Yes — 2,000 min/month |

> ⚠️ **Known limitation**: The Render free tier backend cold-starts in ~30 seconds after inactivity. Document this to evaluators.

---

## 1. Supabase (Database)

1. Create account at [supabase.com](https://supabase.com)
2. New project → choose a region
3. Database → Connection String → copy the PostgreSQL URL
4. Replace `postgres://` with `postgresql+asyncpg://` for async SQLAlchemy
5. Set `DATABASE_URL` in your backend `.env`

---

## 2. Render (Backend)

1. Push code to GitHub
2. New → Web Service → connect your GitHub repo
3. Root directory: `backend`
4. Build command: `pip install -r requirements.txt && alembic upgrade head`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables from `.env.example`
7. Deploy

**Important**: Set `FRONTEND_URL` and `CORS_ORIGINS` to your Vercel frontend URL.

---

## 3. Vercel (Frontend)

1. Import GitHub repo at [vercel.com](https://vercel.com)
2. Root directory: `frontend`
3. Framework: Next.js (auto-detected)
4. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-render-backend-url`
5. Deploy

---

## 4. Resend (Email)

1. Create account at [resend.com](https://resend.com)
2. Add and verify your sending domain (or use the Resend test domain)
3. API keys → Create API key
4. Set `RESEND_API_KEY` and `EMAIL_FROM`

---

## 5. Google Calendar OAuth

See [`google-calendar.md`](google-calendar.md) for the full setup guide.

Quick steps:
1. Google Cloud Console → New project
2. Enable Google Calendar API
3. OAuth consent screen → External → add test users
4. Credentials → OAuth 2.0 Client ID → Web application
5. Authorized redirect URIs: `https://your-backend.render.com/api/v1/calendar/callback`
6. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`

---

## 6. GitHub Actions Scheduler

1. Go to your GitHub repository → Settings → Secrets and variables → Actions
2. Add secrets:
   - `BACKEND_URL`: your Render backend URL
   - `INTERNAL_JOB_SECRET`: same value as in your backend `.env`
3. The `.github/workflows/scheduler.yml` cron fires every 5 minutes automatically

---

## 7. Seed demo data

After deployment, run the seed script once:

```bash
DATABASE_URL=your-supabase-url python scripts/seed.py
```

Or SSH into your Render instance (paid tier) or run locally pointing at Supabase.

---

## 8. Final checklist

- [ ] `ENABLE_LLM=true` + `GEMINI_API_KEY` set
- [ ] `ENABLE_EMAIL=true` + `RESEND_API_KEY` set  
- [ ] `ENABLE_GOOGLE_CALENDAR=true` + Google credentials set
- [ ] `TOKEN_ENCRYPTION_KEY` generated with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] `JWT_SECRET` is a long random string
- [ ] `INTERNAL_JOB_SECRET` set and matches GitHub Actions secret
- [ ] Demo data seeded
- [ ] Evaluator's Google account added as test user in Google Cloud Console
- [ ] Frontend URL in README updated
- [ ] `[SUBMISSION_DEADLINE]` in README replaced
