# SkillGap AI — Resume vs Job Description Skill Gap Analyzer
### Master Plan (v1.0)

A privacy-first, cloud-native web service that uses NLP to compare a student's resume against a job description, surfaces matched/missing skills with a match score, and recommends what to learn next — with zero permanent server-side storage of personal documents.

---

## 1. Product Vision

| | |
|---|---|
| **Problem** | Students don't know which specific skills are blocking them from a role. Generic ATS checkers just count keywords. |
| **Solution** | Semantic (not just keyword) skill-gap analysis: extract skills from both documents using NLP, match them even when worded differently ("ML" vs "Machine Learning"), score the gap, and recommend resources. |
| **Differentiator** | Semantic skill matching (embeddings, not regex), an importance-weighted gap score, and a strict 2-day auto-expiring, privacy-first storage model — no resume ever sits on a server permanently. |
| **Target users** | Students / early-career job seekers, campus placement cells, bootcamps. |

---

## 2. High-Level Architecture

```
┌──────────────────────────────┐        ┌──────────────────────────────────┐
│         FRONTEND (SPA)        │  HTTPS │            BACKEND (API)          │
│  React + Vite + Tailwind      │◄──────►│  FastAPI (Python) — stateless     │
│  IndexedDB (2-day TTL cache)  │  JSON  │  NLP pipeline (async workers)     │
│  Framer Motion animations     │        │  Redis (ephemeral cache, TTL)     │
│  Dark/Light theme             │        │  No permanent document storage    │
└──────────────────────────────┘        └──────────────────────────────────┘
        Deployed: Vercel/Netlify/            Deployed: Cloud Run / Fargate
        Firebase Hosting (CDN)                (containers, auto-scale to 0)
```

**Design principle: "Stateless by default, ephemeral by design."**
- Resume/JD files are parsed in-memory on the backend, the extracted result is returned to the client, and the raw file is discarded immediately after the request (never written to disk).
- The client (browser) is the only place data persists — in **IndexedDB**, tagged with a timestamp, auto-purged after 48 hours by a background sweep on app load + a service worker alarm.
- An optional Redis cache (TTL = 48h) stores only the **anonymized analysis result** (hashed by a random session ID, not tied to identity) so a user can revisit a past comparison from the same browser without re-uploading — this is what satisfies "cloud native" statefulness without violating privacy.

---

## 3. NLP Pipeline (the core value)

Multi-stage pipeline balancing accuracy and speed:

1. **Document ingestion & parsing**
   - Resume: PDF → `pdfplumber` / DOCX → `python-docx`, fallback OCR (`pytesseract`) for scanned PDFs.
   - JD: pasted text or URL scrape (`readability-lxml` + `httpx`).
   - Output: clean plain text + section segmentation (Experience, Skills, Education) via regex + heuristic headers for resumes.

2. **Preprocessing**
   - spaCy (`en_core_web_trf` for accuracy, `en_core_web_sm` fallback for speed) — tokenization, lemmatization, POS tagging, sentence segmentation.

3. **Skill extraction (candidate generation)** — hybrid approach for high accuracy:
   - **Taxonomy matching**: Match text against a curated skills taxonomy (seeded from ESCO + LinkedIn Skills Graph + O*NET, ~30k skills) using `PhraseMatcher`/Aho-Corasick for fast exact + alias matching (handles abbreviations: "JS" → "JavaScript").
   - **Model-based NER**: A transformer NER model fine-tuned for skill extraction (e.g., a `jobbert`/`SkillSpan`-style token classifier, or fine-tune `distilbert-base` on the SkillSpan / Kaggle resume-NER datasets) to catch skills not in the taxonomy (emerging tools, niche frameworks).
   - Candidates from both are merged and deduplicated.

4. **Semantic normalization & matching**
   - Each extracted skill phrase (resume set `R`, JD set `J`) is embedded with `sentence-transformers/all-MiniLM-L6-v2` (fast, 384-dim, strong accuracy/latency tradeoff; upgradeable to `all-mpnet-base-v2` for max accuracy).
   - Cosine similarity matrix between `R` and `J` embeddings. Pairs above a tuned threshold (~0.78) are treated as **matched** even when wording differs ("Data Visualization" ≈ "Dashboarding").
   - Skills in `J` with no match above threshold → **missing skills**.
   - Skills in `R` not in `J` → shown as "bonus/extra skills" (positive signal, not penalized).

5. **Importance weighting**
   - TF-IDF / frequency-of-mention of each skill within the JD, plus a boost if it appears in a "Requirements"/"Must-have" section (detected via section header heuristics) vs "Nice-to-have".
   - Produces a weighted **Match Score (0–100%)**, not a naive skill-count ratio.

6. **Recommendation layer**
   - Each missing skill mapped to 1–2 curated free/low-cost learning resources (a small curated JSON mapping to start; can extend to a live search API).
   - Skills ranked by (importance × ease-of-learning) so the student sees the highest-leverage skill first.

**Accuracy strategy**: start with the taxonomy+embeddings hybrid (fast to ship, ~85%+ precision out of the box), then continuously improve the NER component by fine-tuning on labeled resume/JD data collected (with consent) — this is the "high accuracy NLP model" story: rules give reliability, transformers give recall on novel terms, embeddings give synonym robustness.

---

## 4. API Design (FastAPI)

```
POST   /api/v1/parse/resume        multipart file  -> extracted text + detected skills
POST   /api/v1/parse/jd            text or url      -> extracted text + detected skills
POST   /api/v1/analyze             { resume_skills, jd_skills } -> gap report (matched, missing, score, recommendations)
GET    /api/v1/session/{id}        -> cached analysis (Redis, 48h TTL) for revisit
DELETE /api/v1/session/{id}        -> manual purge
GET    /api/v1/health              -> liveness/readiness probe
```

All endpoints are stateless; `session_id` is a random UUID generated client-side and only used as a Redis cache key.

---

## 5. Data Retention Model ("2-day temp storage")

| Layer | What's stored | TTL | Mechanism |
|---|---|---|---|
| Browser (IndexedDB) | Parsed text, extracted skills, analysis result, timestamps | 48h | Sweep-on-load + `expiresAt` field check before any read; entries past TTL are deleted silently |
| Backend (Redis) | Anonymized analysis JSON keyed by random session UUID | 48h | Native Redis `EX 172800` key expiry |
| Backend (disk) | **Nothing.** Uploaded files exist only as an in-memory buffer during the request | 0 | Never written to disk; garbage collected post-response |

This is called out clearly in the UI (a small "Your data auto-deletes in 48h — nothing is stored on our servers" notice) — a genuine privacy differentiator for a resume tool.

---

## 6. UI/UX Design System — "Light, like Google apps"

**Look & feel reference**: Google Workspace / Material 3 — generous white-space, soft elevation shadows (not heavy borders), rounded 12–16px corners, one accent color used sparingly, instant perceived-performance via skeleton loaders.

- **Typography**: `Google Sans`/`Inter` for UI, `Roboto Mono` for skill chips/scores.
- **Color system** (CSS variables, swap on theme toggle):
  - Light: bg `#FFFFFF`, surface `#F8F9FA`, text `#202124`, accent `#4F46E5` (indigo — distinct from generic Google-blue), success `#1E8E3E`, warning `#F9AB00`, danger `#D93025`.
  - Dark: bg `#121212`, surface `#1E1E1E`, text `#E8EAED`, same accent at slightly higher luminance for contrast.
  - Theme persisted in `localStorage`, respects `prefers-color-scheme` by default.
- **Motion** (Framer Motion):
  - Page transitions: 200ms fade + 8px slide.
  - Upload → analyzing → results: a staged progress animation (parsing → extracting skills → matching → scoring) so the NLP pipeline feels transparent, not a black box.
  - Skill chips animate in with a staggered spring on results reveal (matched = green pop, missing = amber pulse).
  - Match score renders as an animated circular progress ring (0 → score%).
  - Micro-interactions: button press scale (0.97), hover elevation lift, toast slide-ins.
- **Layout**: 3 core screens —
  1. **Upload** — two drop-zones (Resume / JD) side by side, drag-and-drop + paste-text option, big single primary CTA "Analyze Gap".
  2. **Analyzing** — animated pipeline stepper (mirrors section 3 stages) for perceived transparency.
  3. **Results** — top: circular match-score + headline; middle: three columns (Matched / Missing / Bonus skills) as chips; bottom: prioritized recommendation cards with resource links + "Export PDF report" button.
- **Accessibility**: WCAG AA contrast in both themes, full keyboard navigation, `prefers-reduced-motion` respected (animations degrade to simple fades).
- **Responsiveness**: mobile-first, drop-zones stack vertically under 768px.

---

## 7. Cloud-Native Deployment Plan

- **Containerization**: separate `Dockerfile` for frontend (multi-stage build → static Nginx) and backend (slim Python image).
- **Local dev**: `docker-compose.yml` spins up backend + Redis + frontend dev server.
- **Frontend hosting**: static build deployed to Vercel/Netlify/Firebase Hosting — CDN-cached, instant global load.
- **Backend hosting**: FastAPI container on **Google Cloud Run** (or AWS Fargate) — scales to zero when idle (cost-efficient for a student project), autoscale under load.
- **Model serving**: transformer models loaded once at container startup (warm-start), quantized (ONNX/`int8`) to keep cold-start and memory low on serverless containers.
- **CI/CD**: GitHub Actions — lint + test → build Docker images → push to registry → deploy on merge to `main`.
- **Observability**: structured JSON logs, `/health` probe, basic request tracing (OpenTelemetry-ready).
- **Secrets/config**: `.env` locally, cloud provider Secret Manager in production — no secrets in the repo.

---

## 8. Repository Structure

```
skillgap-ai/
├── backend/
│   ├── app/
│   │   ├── api/           # route handlers (v1 endpoints)
│   │   ├── core/          # config, logging, settings
│   │   ├── services/      # resume_parser, jd_parser, skill_extractor, matcher, recommender
│   │   ├── ml/            # model loading, embedding utils, taxonomy data
│   │   ├── models/        # Pydantic schemas
│   │   └── main.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/    # UploadZone, SkillChip, ScoreRing, PipelineStepper, ThemeToggle
│   │   ├── pages/         # Upload, Analyzing, Results
│   │   ├── hooks/         # useIndexedDBStore, useTheme
│   │   ├── context/       # ThemeContext
│   │   ├── lib/           # api client, indexedDB TTL store
│   │   └── styles/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── docker/            # docker-compose.yml
│   ├── k8s/                # optional k8s manifests
│   └── terraform/          # optional IaC for cloud resources
├── docs/
│   └── MASTER_PLAN.md
└── README.md
```

---

## 9. Build Roadmap

| Phase | Scope |
|---|---|
| **0. Scaffold** | Repo structure, Docker, CI skeleton (this deliverable) |
| **1. Core pipeline (MVP)** | Resume/JD parsing, taxonomy skill extraction, exact-match gap report, plain UI |
| **2. Semantic upgrade** | Add embedding-based synonym matching, importance weighting, animated results UI |
| **3. NER upgrade** | Fine-tune/integrate transformer skill-NER for higher recall on novel skills |
| **4. Polish** | Dark mode, full animation pass, PDF export, recommendation engine |
| **5. Cloud-native hardening** | Dockerize, CI/CD, deploy to Cloud Run + CDN frontend, load test |
| **6. Privacy/TTL layer** | IndexedDB 48h store, Redis TTL cache, "data auto-deletes" UX messaging |

---

## 10. Key Risks & Mitigations

- **Skill taxonomy drift** (new tools/frameworks not in taxonomy) → NER model + periodic taxonomy refresh from ESCO/GitHub trending topics.
- **False synonym matches** (embedding threshold too loose) → tune threshold on a labeled validation set, allow manual override in UI ("mark as different skill").
- **Cold-start latency on serverless** (transformer load time) → model quantization + keep-warm ping, or a small always-on min-instance for backend.
- **PDF parsing failures** (scanned/complex layouts) → OCR fallback + clear error state with "paste text instead" option.
