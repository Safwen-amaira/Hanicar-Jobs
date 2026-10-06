# Hanicar Jobs

**Don't search. Hunt.**

AI-powered opportunity discovery and application assistant for PFE, internships, graduate roles, and jobs.

## Stack

- React (Vite) → FastAPI → PostgreSQL
- Redis + Celery workers / scheduler
- Optional LLM providers (Mock / OpenAI-compatible / Ollama / Kaggle). **AI off always works.**

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

## Principles

WORKING > COMPLEX · EXPLAINABLE > MAGIC · SECURE > FAST HACK · GOOD UX > FEATURE COUNT

- Company identity + exclusion engine before collectors
- Scraped content treated as untrusted (delimiter-wrapped for LLM)
- Drafts never auto-send
- LinkedIn / Indeed: user-pasted URLs only - no scraping

## Local backend tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## Design system

See [`design-system/MASTER.md`](design-system/MASTER.md) - charcoal, gold, cinematic Three.js only on landing / SEARCH NOW / match reveal, with reduced-motion fallbacks.

## License

MIT - see `LICENSE` and `NOTICE` (credits Safwen Amaira / Born as root for the original PFE Hunter concept).
