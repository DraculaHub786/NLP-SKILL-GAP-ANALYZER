# SkillGap AI — Build Execution Master Plan
### The order to build in, what "done" means at each step, and the standards to hold it to.

This is the plan you actually execute against. It sequences every file from `FILE_STRUCTURE_MASTER_PLAN.md` into buildable phases, each with a **Definition of Done (DoD)** so nothing ships half-finished, and each gated by tests before the next phase starts. Follow it top to bottom — nothing later depends on something earlier being skipped.

---

## 0. Engineering Standards (apply to every phase below)

These aren't optional polish — treat them as part of the DoD for *every* task, not a final cleanup pass:

| Area | Standard |
|---|---|
| **Version control** | Trunk-based with short-lived feature branches (`feat/skill-extractor`, `fix/pdf-ocr-fallback`). No direct commits to `main`. PR required, CI must pass before merge. |
| **Code style** | Backend: `black` + `ruff` (or `flake8`), type hints on every function signature (already the pattern in the scaffold — keep it consistent). Frontend: `eslint` + `prettier`, no `any` types in TypeScript without a comment justifying it. |
| **Testing** | Every service module gets a matching test file before the module is considered done, not after. Target ≥80% coverage on `backend/app/services/` and `backend/app/ml/` — this is the part that determines product quality. |
| **Commits** | Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) — makes changelogs and version bumps mechanical later. |
| **Secrets** | Never in code or committed `.env`. Local dev uses `.env` (gitignored); cloud uses Secret Manager (GCP) or Secrets Manager (AWS) — wire this in Phase 6, not as an afterthought. |
| **Logging** | Structured JSON logs (`logging` + a JSON formatter, or `structlog`) from Phase 1 onward — retrofitting logging later means blind spots in early phases forever. |
| **Error handling** | Every external call (file parse, model inference, Redis) wrapped with explicit exception handling and a meaningful HTTP status — never let a raw 500 with a stack trace reach the client. |

---

## Phase 1 — NLP Core, No API, No UI
**Goal: prove the extraction and matching logic is correct in isolation, before wiring anything around it.**

### 1.1 Build order
1. `backend/app/ml/skills_taxonomy.json` — expand the seed taxonomy from ~15 entries to a real working set (200–500 skills is a reasonable v1 target; source from ESCO/LinkedIn Skills Graph as noted in the master plan).
2. `backend/app/services/skill_extractor.py` — taxonomy-only extraction first (comment out/stub the NER call). Get this rock-solid before adding NER.
3. `backend/app/services/matcher.py` — semantic matching + scoring.
4. `backend/app/services/resume_parser.py` — PDF/DOCX parsing.

### 1.2 Tests to write (before moving to Phase 2)
- `test_skill_extractor.py`: known-alias resolution ("JS" → "JavaScript"), no-match text returns empty list, case-insensitivity, multi-word skill phrases across a sentence boundary.
- `test_matcher.py`: identical skill sets → 100% match score; disjoint sets → 0%; synonym pair ("ML" resume vs "Machine Learning" JD) → matched above threshold; importance weighting actually shifts the score (a JD with one "must-have" skill weighted higher than three "nice-to-haves" scores lower when the must-have is missing).
- `test_resume_parser.py`: valid PDF → non-empty text, valid DOCX → non-empty text, unsupported extension → raises `ValueError`, corrupt file → doesn't crash the process (caught and re-raised as a clear error).

### 1.3 Definition of Done
- [ ] All three services run standalone via a Python REPL/script with no FastAPI or Redis dependency.
- [ ] Test suite passes with ≥80% coverage on these three files.
- [ ] Taxonomy has enough real-world coverage that a sample tech resume + JD pair produces a sane, manually-verified gap report.
- [ ] Edge cases handled: empty text input, non-English text (documented as out-of-scope for v1, not silently mishandled), resume with no extractable skills.

**Do not proceed to Phase 2 until this phase's tests are green.** The API and UI are just plumbing around this core — if it's wrong here, it's wrong everywhere downstream.

---

## Phase 2 — Backend API
**Goal: expose Phase 1's logic over HTTP, statelessly, with the privacy model enforced from day one.**

### 2.1 Build order
1. `backend/app/core/config.py` — settings object.
2. `backend/app/models/schemas.py` — request/response contracts (write these to match what Phase 1's functions actually return — don't design the API in the abstract).
3. `backend/app/api/v1.py` — routes, wired to Phase 1 services.
4. `backend/app/main.py` — app assembly, CORS.

### 2.2 Tests to write
- `test_api.py` using FastAPI's `TestClient`: each endpoint happy-path, `/parse/resume` with an unsupported file type returns 400 (not 500), `/analyze` with empty skill lists doesn't crash, `/session/{id}` after TTL expiry returns 404, malformed request bodies return 422 automatically (verify Pydantic validation is actually catching bad input).
- **Privacy assertion test**: explicitly assert that after a request to `/parse/resume`, no file exists anywhere under a scratch directory the test points the app at — this is a compliance-relevant test, not a nice-to-have, given the product's privacy promise.

### 2.3 Definition of Done
- [ ] `uvicorn app.main:app --reload` serves all endpoints; `/docs` (Swagger UI) is usable for manual testing.
- [ ] CORS correctly restricts to `allowed_origins` from config (verify a disallowed origin is actually rejected, not just that allowed ones work).
- [ ] Redis TTL is verified with a real Redis instance (`docker run redis:7-alpine`) — key expires at ~48h, confirmed with a short TTL override in a test (e.g. 2 seconds) rather than waiting 48 real hours.
- [ ] Structured logs emitted for every request (method, path, status, latency).
- [ ] No endpoint can write to disk — verified by the privacy assertion test above.

---

## Phase 3 — NER Model (can run in parallel with Phase 4/5 once Phase 1 is solid)
**Goal: add recall on out-of-taxonomy skills without regressing Phase 1's precision.**

### 3.1 Build order
Follow `docs/NER_MODEL_GUIDE.md` exactly:
1. Bootstrap a labeled dataset via distant supervision (run the Phase 1 taxonomy matcher over a batch of real unlabeled JDs/resumes to auto-generate BIO labels).
2. `backend/app/ml/train_ner.py` — train on the bootstrap set, sanity-check on the seed set first.
3. `backend/app/ml/evaluate_ner.py` — measure entity-level F1.
4. `backend/app/ml/ner_inference.py` — production inference wrapper.
5. Re-enable the NER call in `skill_extractor.py`, run the Phase 1 test suite again — it must still pass unchanged (taxonomy hits are never overridden by NER, per the fusion rule).

### 3.2 Tests to write
- `test_ner_inference.py`: model-not-trained case returns `[]` without raising (graceful degradation is load-bearing — the app must work before a model exists).
- `test_skill_extractor.py` (extend): a sentence containing a deliberately out-of-taxonomy skill term is only picked up when NER is enabled, and fusion doesn't produce duplicate/conflicting entries for skills both signals agree on.

### 3.3 Definition of Done
- [ ] Entity-level F1 on a held-out validation split ≥0.70 (bootstrap-tier target from the NER guide; document the actual number achieved).
- [ ] Fusion logic verified not to reduce Phase 1's precision (rerun Phase 1's test suite with NER enabled — same pass rate).
- [ ] Inference latency measured and documented (P50/P95 on a representative sentence length) — this number drives the Phase 6 cold-start decision.
- [ ] Model artifact + tokenizer committed to a model registry or cloud storage bucket (not to git — binary artifacts don't belong in source control).

---

## Phase 4 — Frontend, Static (no live backend calls yet)
**Goal: build and visually verify the entire UI against mocked data before wiring real API calls — catches design/animation issues without backend flakiness in the loop.**

### 4.1 Build order
1. `frontend/src/context/ThemeContext.tsx` — dark/light mode, test the toggle and `prefers-color-scheme` fallback manually in-browser first.
2. `frontend/src/lib/tempStore.ts` — IndexedDB TTL wrapper, **unit test independently of the UI** (this is pure logic).
3. `frontend/src/components/ScoreRing.tsx`, `SkillChip.tsx` — build against hardcoded prop values in isolation (Storybook if you want proper component isolation, or a throwaway test page).
4. `frontend/src/pages/UploadPage.tsx`, `ResultsPage.tsx` — build against a hardcoded mock `GapReport` object matching the Phase 2 schema exactly.
5. `frontend/src/App.tsx` — wire the three-stage state machine, still using the mock data (stub `handleAnalyze` to `setTimeout` + mock report instead of a real `axios` call).

### 4.2 Tests to write
- `tempStore.test.ts`: save → get returns the value; save → manually backdate `expiresAt` → get returns `null` and the entry is gone; `sweepExpired()` removes only expired entries, leaves valid ones.
- Component snapshot/interaction tests (React Testing Library) for `SkillChip` (renders correct variant class) and `ScoreRing` (renders the correct percentage).

### 4.3 Definition of Done
- [ ] Full upload → analyzing → results flow works end-to-end against mock data.
- [ ] Dark mode toggle changes every visible surface correctly (no hardcoded light-only colors slipped in anywhere — do a manual full-page sweep in dark mode).
- [ ] All animations run at 60fps in Chrome DevTools performance panel on a mid-tier device profile (not just on your dev machine).
- [ ] `prefers-reduced-motion` genuinely disables animation (test via OS-level or DevTools emulation, not just the CSS existing).
- [ ] Responsive check: 375px (mobile), 768px (tablet), 1440px (desktop) — no horizontal scroll, no clipped text.
- [ ] Lighthouse accessibility score ≥90 on the Upload and Results pages.

---

## Phase 5 — Integration (frontend ↔ real backend)
**Goal: replace mocks with real calls, and prove the whole system works together, not just its parts.**

### 5.1 Build order
1. Swap `App.tsx`'s mock `handleAnalyze` for the real three-call sequence (`/parse/resume` → `/parse/jd` → `/analyze`) against a locally running backend.
2. Add real error states: network failure, backend 400/500, oversized file upload, empty JD text — every one of these needs a visible, non-cryptic UI state, not a silent console error.
3. Add loading/progress feedback that actually reflects backend stage (upgrade the placeholder "Analyzing skills…" text into the staged pipeline stepper described in the UI/UX design system, now that real stage boundaries exist to hook into).

### 5.2 Tests to write
- End-to-end test (Playwright or Cypress): upload a real sample PDF resume + paste a real JD → assert a results screen renders with a non-zero match score. This is the single most important test in the whole project — it's the one that proves the product actually works, not just its pieces.
- Failure-path E2E: upload a `.txt` file (unsupported) → assert a clear error message, not a blank screen or crash.

### 5.3 Definition of Done
- [ ] Full flow works against `docker compose up` (real backend + Redis + frontend, not dev-mode mocks).
- [ ] Every network failure mode has a designed UI state (checked manually by killing the backend mid-request, throttling network in DevTools, etc.).
- [ ] `docker-compose.yml` (`infra/docker/`) confirmed to spin up a fully working stack from a clean checkout with a single command — this is your smoke test that nothing is secretly relying on your local machine's state.

---

## Phase 6 — Production Hardening & Cloud-Native Deployment
**Goal: what separates "it works on my machine" from an industry-ready service.**

### 6.1 Build order
1. **Secrets**: move `.env` values into GCP Secret Manager / AWS Secrets Manager; update `config.py` if needed to read from the cloud provider's SDK in production mode vs `.env` in dev.
2. **Model deployment**: export the trained NER model to ONNX + quantize (per `NER_MODEL_GUIDE.md` §6); measure the real cold-start impact on Cloud Run before deciding whether `min_instances=1` is needed.
3. **Backend deploy**: build and push the Docker image, deploy to Cloud Run (or Fargate), configure autoscaling, set the `min_instances`/`max_instances` based on the Phase 3 latency numbers.
4. **Frontend deploy**: static build to Vercel/Netlify/Firebase Hosting, environment variable for the deployed backend URL (`VITE_API_BASE`).
5. **Redis**: managed instance (Cloud Memorystore / AWS ElastiCache) — do not run Redis in a container in production, it needs to survive backend restarts.
6. **CI/CD**: extend `.github/workflows/ci.yml` with a deploy job gated on `main` + tests passing — remove the `|| true` on the pytest step now that Phase 1–2 tests exist and should be a hard gate.
7. **Monitoring**: wire the `/health` endpoint into the cloud provider's uptime checks; ship structured logs to Cloud Logging/CloudWatch; add basic alerting on 5xx rate and P95 latency.

### 6.2 Definition of Done — Production Readiness Checklist
- [ ] No secret exists in any committed file, ever (run a secrets scanner like `gitleaks` over the repo history as a final check).
- [ ] HTTPS enforced end-to-end (frontend CDN + backend Cloud Run both terminate TLS by default — verify, don't assume).
- [ ] CORS locked to the actual production frontend origin, not `*`.
- [ ] Rate limiting on the API (even a basic per-IP limit on `/parse/*` and `/analyze` — prevents abuse of the (costly) NLP endpoints).
- [ ] Load test run (e.g. `locust` or `k6`) against a staging deploy — know your actual requests/sec ceiling before real users find it for you.
- [ ] Redis TTL behavior re-verified against the managed instance (config can differ from local Docker Redis).
- [ ] Rollback plan exists (previous Docker image tag retained, one-command redeploy).
- [ ] `README.md` updated with the real production URLs and an accurate "how to deploy" section (not just "how to run locally").

---

## 7. Milestone Summary

| Phase | What exists at the end | Gate to proceed |
|---|---|---|
| 1 — NLP Core | Extraction + matching logic, proven correct standalone | Tests green, ≥80% coverage |
| 2 — Backend API | A real, callable, privacy-respecting API | Tests green, manual `/docs` walkthrough clean |
| 3 — NER Model | Recall beyond the taxonomy, without precision regression | F1 ≥0.70, Phase 1 tests still pass |
| 4 — Frontend (static) | Full UI, animated, themed, accessible — against mock data | Lighthouse ≥90, responsive check passed |
| 5 — Integration | The actual product, working end-to-end | E2E test passes on a clean `docker compose up` |
| 6 — Production | A deployed, monitored, secured, load-tested cloud service | Full checklist in §6.2 checked off |

**This order is deliberate**: it isolates the highest-risk, highest-value part (the NLP accuracy) into a phase you can iterate on with zero API/UI overhead, defers all cloud/deployment complexity to the very end once there's something worth deploying, and never lets the frontend and backend be integrated for the first time under production pressure — Phase 5 is where that risk gets absorbed, deliberately, before Phase 6 raises the stakes.
