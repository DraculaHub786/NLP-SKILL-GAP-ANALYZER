# SkillGap AI → Resume Intelligence Engine

NLP-powered resume analysis engine with three independent sub-scores:
1. **ATS Compatibility Score** — can the file be parsed correctly
2. **Content Quality Score** — is the writing itself strong, regardless of any JD
3. **JD Match Score** — how well resume skills match the job description

See `docs/MASTER_PLAN.md` for the full architecture, NLP pipeline, UI/UX design system, and cloud-native deployment plan.

## Quick start (local dev)

Prereqs:

- Python 3.11
- spaCy model: `python -m spacy download en_core_web_sm`
- (optional, enables semantic synonym matching) `pip install sentence-transformers`
- (optional, enables OCR of scanned PDFs) `pip install pytesseract pypdfium2` + tesseract binary

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# Frontend (new terminal)
cd frontend
npm install
npm run dev

# Or run everything with Docker
cd infra/docker
docker compose up --build
```

Frontend: http://localhost:5173
Backend docs: http://localhost:8080/docs

## Testing

```bash
# Backend unit/integration tests
cd backend && python -m pytest -q

# Frontend unit tests (vitest + RTL)
cd frontend && npm run test

# Typecheck
cd frontend && npm run typecheck

# E2E (Playwright) — boots backend + frontend automatically,
# requires `npx playwright install chromium` once.
cd frontend && npm run e2e
```

## Project structure

```
backend/    FastAPI + NLP pipeline (parsing, skill extraction, 3-engine analysis)
frontend/   React + Vite + Tailwind + Framer Motion, dark mode, IndexedDB 2-day temp store
infra/      docker-compose, k8s manifests, terraform (cloud-native deployment)
docs/       Master plan
```

## Data privacy model

- Uploaded files are parsed in-memory and never written to disk.
- Analysis results are cached anonymously in Redis with a 48h TTL.
- The browser mirrors results in IndexedDB with the same 48h TTL, swept on every app load.

## Score weighting

Sub-scores are weighted independently and configured via JSON, not hardcoded.
Default weights: **ATS 30% / Content 30% / JD Match 40%**

These weights are stored in `backend/app/core/config.py` or can be overridden
per-session via the API. The `overall_score` re-weights automatically when no
JD is provided (ATS + Content only, re-balanced to 50/50).
