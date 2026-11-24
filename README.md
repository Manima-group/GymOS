# Gym-OS — multi-tenant gym management SaaS

Powered by **Manima AI Tech Solutions**. FastAPI + PostgreSQL backend, Next.js frontend, one Docker Compose stack.

## What's inside

| Area | Status |
|---|---|
| Manima Super Admin: tenants, plans/pricing, per-gym feature toggles, global kill switch, limits, SaaS payments, message credits, MRR/ARR, audit log, support access | ✅ Built + tested |
| Single gym & multi-branch owners (same model; 2nd branch auto-converts to multi) | ✅ |
| Roles: owner, manager, front desk, trainer, accountant (branch-scoped) | ✅ |
| Branch QR poster (gym name + branch + area tag + enquiry QR), rotating anti-cheat QR, geofence | ✅ |
| Members, membership plans, renewals, freeze/unfreeze, partial payments & dues | ✅ |
| Payments with per-gym invoice numbers, GST-inclusive tax, printable receipts, CSV export | ✅ |
| Check-in: member QR (phone OTP login), manual desk check-in, staff attendance | ✅ |
| Reminders: renewal (7/3/1 days), expired, dues, birthday, inactive, owner evening summary, SaaS trial/renewal/suspension | ✅ (providers = `log` until credentials are added) |
| Leads CRM (QR enquiry → trial → convert to member) | ✅ |
| Member PWA (`/me`): membership card, visits, payments | ✅ |
| Online payments (Razorpay), trainers/classes, workouts, expenses/POS, AI | ⏳ Phase 3+ (feature keys exist, shown as "coming soon") |

## Recurring revenue built in
- Plans: Basic ₹999, Plus ₹2,499, Premium ₹4,999 a month (yearly = 10× monthly). You can edit them in **Admin → Plans**.
- 14-day trial → suspended automatically if unpaid; paid gyms go `past_due` → `suspended` after a 5-day grace period.
- SMS/WhatsApp **message credits** are deducted per message, so you can sell top-ups as extra income.

## Run locally
```bash
# backend
cd backend && pip install -r requirements-dev.txt && cp .env.example .env
alembic upgrade head
python -m app.seed --admin-email admin@manima.co.in --admin-password 'ChangeMe@123'
TZ=Asia/Kolkata uvicorn app.main:app --reload          # API docs: http://localhost:8000/docs
python -m app.jobs.daily                                 # reminders/billing job (cron hourly)
pytest -q                                                # needs a gymos_test Postgres DB

# frontend
cd frontend && npm i && echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local && npm run dev
```

## Deploy (one VPS)
```bash
cp backend/.env.example backend/.env   # set ENVIRONMENT=prod, a strong JWT_SECRET, PUBLIC_BASE_URL, CORS_ORIGINS
DB_PASSWORD=... PUBLIC_API_URL=https://api.gymos.manima.co.in/api/v1 docker compose up -d --build
docker compose exec api python -m app.seed --admin-email you@manima.co.in --admin-password '...'
```
Put Nginx/Caddy in front for HTTPS and run a nightly `pg_dump` backup.

## Key URLs
`/` landing + pricing • `/signup` gym trial • `/login` • `/app` gym dashboard • `/admin` Manima console • `/c/{BRANCHCODE}` QR check-in • `/c/{code}/join` enquiry • `/me` member app

## Architecture notes
- Modular monolith: `backend/app/modules/*` (auth, onboarding, platform, branches, members, billing, attendance, reports, notify).
- Tenant isolation: every tenant table has `org_id`. All access goes through `TenantContext.owned()` / `branch_filter()`, and `require(perm, feature)` checks RBAC, plan features and suspension on the server.
- Features resolve as plan defaults → per-tenant override → global kill switch (`core/entitlements.py`).
- Business timezone: IST (DB session + container `TZ`).
- AI-ready: clean event tables (attendance, payments, notifications), an `ai` feature flag, and Postgres (add `pgvector` when needed).

## Before going live
1. Notification providers: SMTP/SES for email; MSG91 for SMS (**DLT registration required**); WhatsApp Cloud API or a BSP (**approved templates required**). Plug them into `modules/notify.py`.
2. Add rate limiting on `/auth/*` and `/public/*` at Nginx (OTP and signup abuse).
3. Razorpay for gym subscriptions + member online payments (Phase 3).
