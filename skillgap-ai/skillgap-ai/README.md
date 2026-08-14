# SkillGap AI

NLP-powered resume vs job-description skill gap analyzer. See `docs/MASTER_PLAN.md` for the full architecture, NLP pipeline, UI/UX design system, and cloud-native deployment plan.

## Quick start (local dev)

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
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

## Project structure

```
backend/    FastAPI + NLP pipeline (parsing, skill extraction, semantic matching)
frontend/   React + Vite + Tailwind + Framer Motion, dark mode, IndexedDB 2-day temp store
infra/      docker-compose, k8s manifests, terraform (cloud-native deployment)
docs/       Master plan
```

## Data privacy model

- Uploaded files are parsed in-memory and never written to disk.
- Analysis results are cached anonymously in Redis with a 48h TTL.
- The browser mirrors results in IndexedDB with the same 48h TTL, swept on every app load.
