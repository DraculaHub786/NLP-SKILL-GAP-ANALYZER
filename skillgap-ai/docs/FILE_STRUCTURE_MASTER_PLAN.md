# SkillGap AI — File & Folder Master Plan

A complete, file-by-file blueprint of the project. Every entry below states **what the file is, why it exists, and what depends on it** — use this as the single reference when building, reviewing, or onboarding someone else onto the repo.

---

## 0. Top-Level Layout

```
skillgap-ai/
├── backend/            NLP + API service (FastAPI, Python)
├── frontend/            Web client (React, Vite, Tailwind)
├── infra/                Deployment: Docker, CI/CD, cloud IaC
├── docs/                 Planning & model documentation
├── .github/workflows/    CI pipeline
└── README.md
```

**Build order recommendation**: `backend/app/ml` (taxonomy + schemas) → `backend/app/services` → `backend/app/api` + `main.py` → `frontend` → `infra`. NLP logic has no UI dependency, so it can be built and tested standalone first.

---

## 1. `backend/` — NLP + API Service

### 1.1 Root files

| File | Purpose |
|---|---|
| `requirements.txt` | Pinned Python dependencies. Split conceptually into **API deps** (fastapi, uvicorn, pydantic), **parsing deps** (pdfplumber, python-docx, pytesseract), **NLP deps** (spacy, sentence-transformers, scikit-learn), **NER training deps** (torch, transformers, datasets, seqeval, accelerate, optimum), and **infra deps** (redis, httpx, readability-lxml, python-dotenv). |
| `Dockerfile` | Builds the production backend image: installs system deps (tesseract-ocr for OCR fallback), installs Python deps, downloads the spaCy `en_core_web_sm` model at build time (not runtime, so cold starts don't re-download), runs `uvicorn` on port 8080. |
| `.env.example` | Template for local secrets/config: `REDIS_URL`, `SESSION_TTL_SECONDS` (172800 = 48h), `ALLOWED_ORIGINS` (CORS), `EMBEDDING_MODEL`, `SKILL_MATCH_THRESHOLD`. Copy to `.env` for local dev; real `.env` is gitignored. |

### 1.2 `backend/app/` — application package

| File | Purpose | Depends on |
|---|---|---|
| `main.py` | FastAPI app entrypoint. Instantiates `FastAPI()`, wires CORS middleware from `core/config.py`, includes the `v1` router. This is what `uvicorn app.main:app` runs. | `api/v1.py`, `core/config.py` |
| `__init__.py` (in every subfolder) | Marks each directory as an importable Python package. No logic. | — |

#### `backend/app/core/` — configuration

| File | Purpose |
|---|---|
| `config.py` | Single `Settings` object (pydantic-settings) reading from `.env`. Holds `redis_url`, `session_ttl_seconds`, `allowed_origins`, `embedding_model`, `skill_match_threshold`. Every other module that needs config imports `settings` from here — **one source of truth**, no scattered `os.environ` calls. |

#### `backend/app/models/` — data contracts

| File | Purpose |
|---|---|
| `schemas.py` | Pydantic request/response models: `ExtractedSkills` (raw text + skill list), `AnalyzeRequest` (resume/JD skill lists in), `SkillMatch` (one matched pair + similarity score), `Recommendation` (missing skill + resources), `GapReport` (the full API response: score, matched, missing, bonus, recommendations). These models define the **API contract** the frontend codes against. |

#### `backend/app/services/` — business logic (the NLP pipeline, orchestration layer)

| File | Purpose | Depends on |
|---|---|---|
| `resume_parser.py` | Converts an uploaded resume file (bytes, in-memory only — never written to disk) into plain text. `parse_pdf()` uses `pdfplumber`; falls back to `_ocr_fallback()` for scanned PDFs with no extractable text. `parse_docx()` uses `python-docx`. `parse_resume()` is the public dispatcher by file extension. | `pdfplumber`, `python-docx` |
| `skill_extractor.py` | The hybrid extraction engine. Loads the spaCy pipeline + a `PhraseMatcher` built from `ml/skills_taxonomy.json` at import time (once, not per-request). `extract_skills(text)` runs taxonomy matching (exact + alias + noun-chunk heuristics) **and** calls the fine-tuned NER model (`ml/ner_inference.py`), then fuses both signals: taxonomy hits are always kept (precise), NER hits are added only when they introduce a genuinely new skill not already in the taxonomy set. | `spacy`, `ml/skills_taxonomy.json`, `ml/ner_inference.py` |
| `matcher.py` | The semantic gap-scoring engine. Loads a `SentenceTransformer` model at import time. `compute_gap_report()` embeds resume skills and JD skills, computes cosine similarity, matches pairs above `settings.skill_match_threshold` (catches synonyms like "ML" ≈ "Machine Learning"), computes an importance-weighted match score, and builds the ranked `recommendations` list. Returns a `GapReport`. | `sentence-transformers`, `models/schemas.py`, `core/config.py` |

#### `backend/app/api/` — HTTP layer

| File | Purpose |
|---|---|
| `v1.py` | All versioned API routes, thin wrappers around the services above: `POST /parse/resume` (file → `ExtractedSkills`), `POST /parse/jd` (text → `ExtractedSkills`), `POST /analyze` (skill lists → `GapReport`, also writes an anonymized copy to Redis with a 48h TTL), `GET /session/{id}` and `DELETE /session/{id}` (revisit/purge a cached report), `GET /health` (liveness probe for Cloud Run / k8s). This file should stay thin — no NLP logic lives here, only orchestration + HTTP concerns. |

#### `backend/app/ml/` — models, data, and training pipeline

| File / Folder | Purpose |
|---|---|
| `skills_taxonomy.json` | The seed skill taxonomy: `{canonical_skill: [aliases]}`. This is what `skill_extractor.py`'s `PhraseMatcher` is built from. Meant to be grown over time (from ESCO, LinkedIn Skills Graph, or auto-promoted high-confidence NER discoveries). |
| `data/skill_ner_seed.jsonl` | Hand-written BIO-tagged sentences (`{"tokens": [...], "tags": [...]}` per line) used to smoke-test the training/eval pipeline end-to-end. **Not** meant to train a production model on its own — swap in real data per the tiered strategy in `docs/NER_MODEL_GUIDE.md` before training for real. |
| `train_ner.py` | Fine-tunes a `distilbert-base-uncased` token-classification model on BIO-tagged data using HuggingFace `Trainer`. CLI: `--data`, `--base_model`, `--epochs`, `--batch_size`, `--lr`, `--out`. Saves the trained model + tokenizer to `model_artifacts/`. |
| `evaluate_ner.py` | Loads a trained model, runs it over a labeled dataset, prints entity-level precision/recall/F1 via `seqeval` (span-level metric — the correct one for this task, unlike token-level accuracy). |
| `ner_inference.py` | Production inference wrapper. Lazily loads the trained model **once** as a module-level singleton (not per-request — critical for latency). `extract_skills_ner()` returns skill spans with confidence scores. Degrades gracefully to an empty list if no model has been trained yet, so the rest of the app keeps working on taxonomy matching alone. |
| `model_artifacts/` | Where the trained model + tokenizer are saved after running `train_ner.py`. Gitignored (models are binary artifacts, not source) — regenerate via training, or pull from a model registry/cloud storage bucket in production. |

#### `backend/app/utils/`

| File | Purpose |
|---|---|
| `__init__.py` | Currently empty — reserved for shared helpers (e.g. text cleaning, logging setup) that don't belong to a single service, to avoid duplicating small utility functions across `services/`. |

#### `backend/tests/`

| File | Purpose |
|---|---|
| `__init__.py` | Marks the test package. Reserved for `pytest` unit tests — one file per service module is the intended convention (`test_skill_extractor.py`, `test_matcher.py`, `test_resume_parser.py`, `test_api.py` for endpoint-level tests via `TestClient`). |

---

## 2. `frontend/` — Web Client

### 2.1 Root config files

| File | Purpose |
|---|---|
| `package.json` | Dependencies: `react`, `react-dom` (UI), `framer-motion` (animation), `idb` (IndexedDB wrapper), `axios` (API calls). Dev deps: Vite, TypeScript, Tailwind, PostCSS, Autoprefixer. |
| `vite.config.ts` | Vite build config — React plugin, dev server on port 5173. |
| `tailwind.config.js` | Design tokens: `darkMode: "class"` (toggled via `ThemeContext`), `accent` color (`#4F46E5`), `surface.light`/`surface.dark`, `xl2` border-radius (16px) for the Google-Workspace-style rounded cards. |
| `postcss.config.js` | Wires Tailwind + Autoprefixer into the CSS build pipeline. |
| `index.html` | HTML shell — single `#root` mount point, loads `src/main.tsx` as a module script. |
| `Dockerfile` | Multi-stage build: Node stage runs `npm run build` (static Vite output), then copies `dist/` into a slim `nginx:alpine` image to serve as static files in production. |

### 2.2 `frontend/src/`

| File / Folder | Purpose | Depends on |
|---|---|---|
| `main.tsx` | React root entrypoint — mounts `<App />` into `#root`, imports global styles. | `App.tsx`, `styles/index.css` |
| `App.tsx` | Top-level state machine: `upload → analyzing → results`. Owns the `report` state, calls the backend (`/parse/resume`, `/parse/jd`, `/analyze` in sequence), saves the result to IndexedDB, sweeps expired temp-store entries on mount, wraps everything in `ThemeProvider` and animates stage transitions with `AnimatePresence`. | `pages/UploadPage.tsx`, `pages/ResultsPage.tsx`, `context/ThemeContext.tsx`, `lib/tempStore.ts` |
| `styles/index.css` | Tailwind directives + base font stack (`Inter`/`Google Sans`) + a `prefers-reduced-motion` override that kills animation duration for accessibility. | — |
| `context/ThemeContext.tsx` | Dark/light mode provider. Reads saved preference from `localStorage`, falls back to OS `prefers-color-scheme`, toggles the `dark` class on `<html>` (which Tailwind's `darkMode: "class"` picks up). Exposes `useTheme()` hook. | — |
| `lib/tempStore.ts` | The 48-hour client-side data retention layer. Wraps `idb` to open a `skillgap-temp-store` IndexedDB database. `saveTemp()`/`getTemp()` read/write with an `expiresAt` timestamp; `getTemp()` auto-deletes and returns `null` past TTL; `sweepExpired()` (called once on app load in `App.tsx`) purges all stale entries. This is what makes the "auto-deletes in 48h" privacy promise real, not just UI copy. | `idb` |
| `components/ScoreRing.tsx` | Animated circular progress ring (SVG `stroke-dashoffset` + Framer Motion) showing the overall match score, with a fade-in percentage label. Pure presentational component — takes `score: number`. | `framer-motion` |
| `components/SkillChip.tsx` | Pill-shaped skill tag with a spring stagger-in animation. Three color variants (`matched` = green, `missing` = amber, `bonus` = indigo) driving both color and semantic meaning. | `framer-motion` |
| `pages/UploadPage.tsx` | Screen 1: resume drop-zone (file input), JD paste textarea, theme toggle button, "Analyze Gap" CTA (disabled until both inputs are present), and the 48h data-retention disclaimer text. Calls `onAnalyze(file, jdText)` passed down from `App.tsx`. | `context/ThemeContext.tsx` |
| `pages/ResultsPage.tsx` | Screen 3: renders `ScoreRing`, then three animated sections of `SkillChip`s (Matched / Missing / Bonus), then a recommendations list with links out to learning resources. Purely presentational — takes a `report` prop shaped like the backend's `GapReport`. | `components/ScoreRing.tsx`, `components/SkillChip.tsx` |

*(Screen 2, "Analyzing", is currently inlined directly in `App.tsx` as a simple pulsing status message — a natural next upgrade is to extract it into its own `pages/AnalyzingPage.tsx` with the animated pipeline stepper described in the master plan's UI/UX section, mirroring the actual backend stages: parsing → extracting → matching → scoring.)*

---

## 3. `infra/` — Deployment

| File / Folder | Purpose |
|---|---|
| `docker/docker-compose.yml` | Local multi-service orchestration: `redis` (cache), `backend` (built from `../../backend/Dockerfile`), `frontend` (built from `../../frontend/Dockerfile`, served via nginx on port 5173→80). One command (`docker compose up --build`) runs the entire stack locally. |
| `k8s/` | Reserved for Kubernetes manifests (Deployment, Service, Ingress, HorizontalPodAutoscaler) if/when the project outgrows a single Cloud Run service — currently just a placeholder (`.gitkeep`). |
| `terraform/` | Reserved for Infrastructure-as-Code (Cloud Run service definition, Redis instance, networking, Secret Manager entries) — currently just a placeholder (`.gitkeep`). |

---

## 4. `.github/workflows/`

| File | Purpose |
|---|---|
| `ci.yml` | Two parallel jobs on every push/PR to `main`: **backend** — installs Python deps, downloads the spaCy model, runs `pytest` (currently non-blocking via `|| true` until real tests are added — remove that once `backend/tests/` has coverage); **frontend** — installs npm deps, runs `npm run build` to catch build breaks. This is the gate before deploying via the Dockerfiles above. |

---

## 5. `docs/`

| File | Purpose |
|---|---|
| `MASTER_PLAN.md` | The product-and-architecture master plan: vision, high-level architecture diagram, the NLP pipeline stages, API design, data retention model, UI/UX design system, cloud-native deployment plan, and build roadmap. Read this first for **why** the system is shaped this way. |
| `NER_MODEL_GUIDE.md` | Deep-dive on the skill-NER model specifically: BIO tagging scheme, the three-tier data-sourcing strategy (distant supervision → public datasets → active learning), training/evaluation commands, fusion logic with the taxonomy matcher, and ONNX deployment notes for Cloud Run cold-starts. |
| *(this file)* | File-by-file blueprint of the entire repo — the map for **where** each piece of the plan above actually lives in code. |

---

## 6. Cross-Cutting Notes

- **Privacy by construction, not just policy**: no file in `backend/` ever writes an uploaded document to disk — trace this yourself by noting `resume_parser.py` only ever operates on in-memory `bytes`, and `api/v1.py`'s `/analyze` endpoint only ever persists the already-anonymized `GapReport` (not raw text) to Redis.
- **Two independently swappable NLP stages**: `skill_extractor.py` (extraction) and `matcher.py` (semantic comparison) are decoupled — you can upgrade the embedding model in `matcher.py` or retrain the NER model in `ml/` without touching the other.
- **Frontend has zero business logic**: every page component (`UploadPage`, `ResultsPage`) is presentational and receives data/callbacks as props — all orchestration lives in `App.tsx`, all persistence logic lives in `lib/tempStore.ts`. This keeps the components easy to test or restyle independently.
