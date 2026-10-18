# PropPulse AI — Autonomous Real Estate Sales & Client Lifecycle Agent

An AI sales & account executive that runs the whole real estate customer lifecycle 24/7:

| Workstream | Priority | What the agent does |
| --- | --- | --- |
| Inbound lead qualification & booking | P0 | Telegram chat agent (Gemini 3.8 Flash function calling) answers property questions from live inventory, qualifies budget/preferences, and books calls or site visits on Google Calendar with Telegram + email confirmations. |
| Phonebook & buyer ledger CRM | P0 | Automatically extracts names, phones, emails, budgets and preferences from conversations into Supabase; tracks contracts and monthly installment schedules. |
| Ad publishing & targeted broadcasts | P1 | Parses company announcements (portal or inbound email), updates inventory, writes ad copy, posts to the Telegram channel with inquiry buttons, and messages matching leads by Telegram + email. |
| Proactive reminders | P1 | Daily Cloud Scheduler job: 24h meeting reminders (with location pin) and personalized installment invoices for buyers due within 3 days or overdue. |

```
Company announcement / email ─┐          ┌── GCP Cloud Scheduler (daily cron)
                              ▼          ▼
                     FastAPI backend (Cloud Run) ◄──► Next.js Sales Command Center
                     │        │         │
   Gemini 3.8 Flash ◄┘   Supabase PG    └─► Telegram Bot & Channel · Google Calendar · Resend
   (function calling)   (CRM, inventory, appointments, ledger, activity log)
```

## Repository layout

```
backend/                 FastAPI app (Python 3.12+)
  app/agent/             Gemini tools (search_properties, upsert_client_profile,
                         check_calendar_availability, book_appointment) + function-calling loop
  app/workflows/         ingestion.py (WF1) · conversation.py (WF2) · proactive.py (WF3)
  app/services/          gemini · telegram · calendar · email (Resend)
  app/routers/           telegram webhook · ingest · cron · web chat · admin API
  app/poller.py          local Telegram long-polling (no public URL needed)
  tests/                 pytest suite with in-memory fakes for every external service
frontend/                Next.js 16 + Tailwind + Lucide dashboard
supabase/migrations/     0001_init.sql — schema
supabase/seed.sql        demo inventory, leads, a buyer with an overdue installment
deploy/                  Cloud Run, Cloud Scheduler and Telegram webhook scripts
```

## 1. Set up the external services (all free tiers)

1. **Supabase** — create a project → SQL editor → run `supabase/migrations/0001_init.sql`, then (optionally) `supabase/seed.sql`.
   Copy the project URL and the **service_role** key (Project Settings → API).
2. **Gemini** — create an API key at Google AI Studio.
3. **Telegram** — create a bot with @BotFather (token). Create a public channel and add the bot as an **administrator** with "Post messages". `TELEGRAM_CHANNEL_ID` is `@channelhandle` (or the numeric `-100…` id).
4. **Google Calendar** — in a GCP project enable the Calendar API, create a service account and download its JSON key. In Google Calendar, share the sales calendar with the service-account email ("Make changes to events"), and copy the calendar ID (Settings → Integrate calendar).
   *A service account can't invite attendees without Workspace domain-wide delegation, so PropPulse sends confirmations itself via Telegram + Resend instead.*
5. **Resend** — create an API key. With the default `onboarding@resend.dev` sender, Resend only delivers to **your own account email**. To email real clients, verify a domain and set `EMAIL_FROM=Sales <sales@yourdomain.com>`.

## 2. Run locally

```bash
# Backend
cp .env.example backend/.env          # fill in the values from step 1
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload --port 8000

# Telegram (second terminal) — long-polling instead of a webhook while developing
cd backend && .venv/bin/python -m app.poller

# Dashboard (third terminal)
cd frontend
cp .env.local.example .env.local      # BACKEND_URL + the same ADMIN_API_KEY as the backend
npm install && npm run dev            # http://localhost:3000
```

API docs: http://localhost:8000/docs

### Try the workflows

- **Lead qualification:** open your bot on Telegram (or the dashboard's *Agent Test Chat*) and chat like a buyer:
  "Hi, what 2-bedroom apartments do you have in Bole?" → "I'm Abebe, 0911…, abebe@mail.com, budget 10M" →
  "Can I visit on Thursday?" Watch tool calls stream into the *Command Center* feed, the profile fill in the *Phonebook*, and an event appear on Google Calendar.
- **Ad & broadcast:** *Ad & Broadcast* → load a sample → *Analyze with Gemini* → review → *Publish & broadcast*. The ad goes to your channel with deep-link buttons (`t.me/<bot>?start=prop_<id>` opens a chat already about that property), and leads whose budget/bedrooms/location match get a personal Telegram message + email.
- **Proactive reminders:** to receive them yourself, chat with the bot first (so you exist as a client with a Telegram chat id), set your email in your Phonebook record, then *Meetings & contracts → Record a sale* with a first due date within 3 days. Click *Automations → Run now* (or book a visit for tomorrow). Running twice the same day sends nothing new; reminders are de-duplicated.
- **Inbound email:** POST any inbound-email webhook payload (Resend, Postmark, Mailgun, CloudMailin, Zapier…) to
  `/api/ingest/email-webhook?token=$INGEST_WEBHOOK_SECRET`.

### Tests

```bash
cd backend && .venv/bin/python -m pytest
```

## 3. Deploy (GCP Always Free + Vercel)

```bash
# Backend → Cloud Run (requires gcloud auth login)
PROJECT_ID=my-project REGION=us-central1 ./deploy/cloudrun-deploy.sh
./deploy/set-telegram-webhook.sh https://proppulse-api-xxxx.run.app
PROJECT_ID=my-project REGION=us-central1 ./deploy/scheduler.sh https://proppulse-api-xxxx.run.app
```

- Telegram updates are processed inside the webhook request (not as a background task), so Cloud Run keeps CPU allocated with request-based billing and `min-instances=0`.
- The scheduler job calls `POST /api/cron/daily-proactive-run` at 07:00 local time with the `X-Cron-Secret` header.
- **Dashboard:** deploy `frontend/` to Vercel (or Cloud Run) with `BACKEND_URL` and `ADMIN_API_KEY` env vars, then set `FRONTEND_ORIGIN` on the backend.
  The browser never sees the admin key; the Next.js route `/api/backend/*` proxies to FastAPI and adds it server-side.

## Configuration reference

See `.env.example`. Notable settings: `TIMEZONE` (default `Africa/Addis_Ababa`), `CURRENCY` (`ETB`), `BUSINESS_HOURS_START/END`, `WORKING_DAYS` (Mon=0…Sun=6), `AGENT_NAME`, `COMPANY_NAME`, `SALES_OFFICE_ADDRESS`.

## Security notes

- Admin, chat and ingest endpoints require `X-Admin-Key` (if `ADMIN_API_KEY` is unset the backend logs a warning and leaves them open, which is for local dev only).
- The Telegram webhook verifies `X-Telegram-Bot-Api-Secret-Token`; cron requires `X-Cron-Secret`; email ingest requires `?token=`.
- All tables have RLS enabled with no policies; only the backend's service-role key can access them.
