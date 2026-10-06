# Hanicar Jobs

**Don't search. Hunt.**

Hanicar Jobs is a full-stack opportunity hunting and application CRM for PFE projects, internships, graduate roles, freelance work, and full-time jobs. It collects public opportunities, ranks them against a candidate profile, drafts truthful ATS-friendly application material with an optional LLM, exports CV/cover-letter PDFs, and tracks every application from draft to offer or rejection.

## What Is Implemented

- **Opportunity discovery**
  - Public-source collectors for Remotive, Arbeitnow, RemoteOK, Jobicy, and The Muse.
  - Web radar search from the Opportunities page.
  - RSS and manual public URL collector support in the backend.
  - Duplicate detection using stable content hashes.
  - Company identity normalization and alias handling.

- **Candidate and search profiles**
  - Candidate records with locale support.
  - CV text, skills, preferences, uploaded CV attachment, and uploaded cover-letter attachment.
  - Search profiles with keywords, locations, and opportunity type filters.
  - Built-in opportunity types for PFE, internships, junior roles, remote-only, contract, freelance, part-time, and full-time.

- **Matching and filtering**
  - Explainable match scores.
  - Match reasons shown per opportunity.
  - CV skill-gap detection.
  - Suppression/exclusion decisions with auditable reasons.
  - Contact history safeguards so previously contacted/applied companies can be excluded.

- **Applications CRM**
  - Board and list views.
  - Status pipeline: `draft`, `prepared`, `queued`, `sent`, `applied`, `interviewing`, `offer`, `rejected`, `withdrawn`, `failed`.
  - Applied, interview, decision, next-action, and follow-up dates.
  - Recruiter/contact name and email fields.
  - Notes per application.
  - Follow-up draft generation.
  - Email composer with explicit user-controlled sending.
  - SMTP settings and SMTP test flow.

- **LLM-assisted drafting**
  - Provider abstraction for Mock, OpenAI-compatible APIs, Ollama, and Kaggle placeholder mode.
  - Cached LLM responses in the database.
  - Prompt injection boundaries around untrusted job/source content.
  - Application draft creation and regeneration.
  - Tone controls in the application workspace.
  - AI can be fully disabled; template mode still works.

- **ATS-friendly PDFs**
  - Cover-letter PDF generation per application.
  - CV PDF generation from candidate profile text and skills.
  - Plain-text, ATS-oriented layouts.
  - Uploaded CV and cover-letter attachment support for email sending.

- **UI/UX**
  - React/Vite frontend with a richer SaaS-style dashboard.
  - Applications CRM workspace with board/list toggle, metrics, AI draft studio, PDF actions, dates, contacts, and notes.
  - Opportunities page with advanced filters, CSV export, score sorting, and web radar search.
  - Dashboard, profile setup, search run page, sources health, settings, suppressed opportunities, and about page.
  - English, French, and Arabic locale switching.

- **Operational pieces**
  - FastAPI backend.
  - PostgreSQL persistence.
  - Redis and Celery worker/scheduler services.
  - Docker Compose stack.
  - Startup database compatibility shim for newly added application tracker columns.
  - Backend tests and frontend production build verified locally.

## Stack

- **Frontend:** React, Vite, TypeScript, Three.js landing/search visuals.
- **Backend:** FastAPI, SQLAlchemy async, Pydantic.
- **Database:** PostgreSQL.
- **Jobs:** Redis, Celery worker, Celery beat scheduler.
- **PDF:** ReportLab.
- **LLM:** Mock, OpenAI-compatible chat completions, Ollama, Kaggle placeholder.

## Quick Start

```bash
cp .env.example .env
bash scripts/compose.sh up --build
```

Open:

- Frontend: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health>

Stop the stack:

```bash
bash scripts/compose.sh down
```

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

By default the frontend expects the API on the same origin when served by Docker. For local split development, set:

```bash
VITE_API_BASE=http://localhost:8000
```

## Environment

The app reads backend settings from `.env` using the `HJ_` prefix.

Important settings:

```bash
HJ_AI_ENABLED=false
HJ_LLM_PROVIDER=mock
HJ_OPENAI_API_KEY=
HJ_OPENAI_BASE_URL=https://api.openai.com/v1
HJ_OPENAI_MODEL=gpt-4o-mini
HJ_OLLAMA_BASE_URL=http://localhost:11434
HJ_OLLAMA_MODEL=llama3.2

HJ_SMTP_HOST=smtp.gmail.com
HJ_SMTP_PORT=587
HJ_SMTP_USERNAME=
HJ_SMTP_PASSWORD=
HJ_SMTP_FROM_EMAIL=
HJ_SMTP_FROM_NAME=Hanicar Jobs
```

LLM providers:

- `mock`: no external AI call; deterministic template fallback.
- `openai`: any OpenAI-compatible `/chat/completions` API.
- `ollama`: local Ollama `/api/generate`.
- `kaggle`: placeholder provider that falls back to template mode unless extended.

## Main Workflow

1. Create a candidate in **Profiles**.
2. Add CV text, skills, preferences, and optional CV/cover-letter PDFs.
3. Create a search profile with keywords, locations, and opportunity types.
4. Run **SEARCH NOW**.
5. Review ranked opportunities and explanations.
6. Use **Web opportunity radar** for additional public-source searches.
7. Open an opportunity and create an application draft.
8. Manage the application in **Applications CRM**.
9. Regenerate the draft with the LLM studio if desired.
10. Export ATS CV/cover-letter PDFs or compose an email.
11. Track dates, contacts, notes, follow-ups, interviews, offers, and outcomes.

## Safety Principles

- The app never auto-sends applications.
- Sending email requires explicit user action.
- Job descriptions and scraped/public content are treated as untrusted.
- LLM prompts are wrapped with clear untrusted-content delimiters.
- LinkedIn and Indeed are not scraped; use user-pasted public URLs only.
- Application PDFs use plain ATS-friendly text layouts.

## Verification

Backend tests:

```bash
cd backend
./.venv/bin/pytest
```

Frontend TypeScript check:

```bash
cd frontend
/bin/node ./node_modules/typescript/bin/tsc -b --pretty false
```

Frontend production build:

```bash
cd frontend
/bin/node ./node_modules/vite/bin/vite.js build
```

Latest local verification:

- Backend tests: `7 passed`.
- TypeScript build: passed.
- Vite production build: passed.

## API Highlights

- `GET /api/health`
- `GET /api/opportunities`
- `POST /api/opportunities/web-search`
- `GET /api/opportunities/{id}`
- `POST /api/search/{profile_id}/run`
- `GET /api/search/runs/{run_id}`
- `GET /api/search/runs/{run_id}/events`
- `GET /api/applications`
- `POST /api/applications`
- `PATCH /api/applications/{id}`
- `POST /api/applications/{id}/regenerate`
- `GET /api/applications/{id}/email`
- `POST /api/applications/{id}/send-email`
- `GET /api/applications/{id}/cover-letter.pdf`
- `GET /api/applications/{id}/cv.pdf`
- `GET /api/applications/due/follow-ups`
- `GET /api/sources/health`

## Project Layout

```text
backend/
  app/
    api/           FastAPI routers
    collectors/    Public opportunity collectors
    core/          Settings and security helpers
    db/            Session, base, seeds
    llm/           Provider abstraction and cache
    models/        SQLAlchemy models
    services/      Matching, applications, identity, exclusion, pipeline
    workers/       Celery worker setup
  tests/

frontend/
  src/
    components/    App shell
    cinematic/     Three.js scenes
    pages/         Dashboard, profiles, hunt, opportunities, applications, sources, settings
    api.ts         Frontend API client
    styles.css     SaaS UI system
```

## Design Direction

Hanicar Jobs uses a restrained premium SaaS interface: charcoal navigation, warm gold accents, dense operational views, explainable metrics, and workflow-first screens. The app is meant to feel like a command center for opportunity hunting rather than a generic job-board clone.

## License

MIT. See `LICENSE` and `NOTICE`.

Credits: Safwen Amaira / Born as root for the original PFE Hunter concept.
