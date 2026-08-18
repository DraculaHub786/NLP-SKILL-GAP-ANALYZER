# Skill-NER Model — Build Guide

This is the piece that pushes skill extraction past taxonomy-matching alone: a
token-classification model that recognizes skill mentions **even when they're
not in the taxonomy** (a brand-new framework, a niche tool, an unusual phrasing).

The taxonomy matcher (`skill_extractor.py`, phase 1) stays as the reliable
backbone. This model is the *recall booster* layered on top. In production the
two are fused — see §5.

---

## 1. Task framing

Standard **BIO-tagged token classification**, one entity type: `SKILL`.

```
Built   O
data    B-SKILL
pipelines I-SKILL
using   O
Apache  B-SKILL
Airflow I-SKILL
and     O
dbt     B-SKILL
.       O
```

- `B-SKILL` = first token of a skill span, `I-SKILL` = continuation, `O` = not a skill.
- Base model: `distilbert-base-uncased` (fast, small — good for Cloud Run cold starts).
  Swap in `bert-base-uncased` or a domain model like `jjzha/jobbert-base-cased`
  if you want higher accuracy and can accept a bigger container.

---

## 2. Getting labeled data (the real bottleneck)

Hand-labeling thousands of resumes is unrealistic for a solo/small-team build.
Use this **three-tier strategy**, cheapest first:

### Tier 1 — Distant supervision (bootstrap, do this first)
Run the existing `PhraseMatcher` taxonomy matcher (already built) over a large
pile of **unlabeled** resumes/JDs to auto-generate BIO labels. Every taxonomy
hit becomes a `B-SKILL`/`I-SKILL` span; everything else is `O`. This is noisy
(misses out-of-taxonomy skills — the exact thing you're trying to teach the
model to catch) but it's free, fast, and gives the model a strong prior on
what a "skill span" looks like grammatically/positionally, which transfers to
novel terms too.

*Sources for the unlabeled raw text*: public job postings (e.g. scrape a few
hundred JDs with `httpx` + `readability-lxml`, already a backend dependency),
anonymized sample resumes (Kaggle's "Resume Dataset" — search it directly on
kaggle.com), your own internship reconnaissance corpus if applicable.

### Tier 2 — Public NER-for-skills datasets (real gold labels)
Academic datasets exist and are the highest-value addition:
- **SkillSpan** (Zhang et al.) — sentence-level skill span annotations from job ads.
- **Kaggle "Resume NER Dataset"** — pre-tagged resume entities including skills.
- **JobBERT / ESCO-linked corpora** — skill mentions linked to the ESCO taxonomy.

Search each by name on Kaggle / Hugging Face Datasets Hub and merge into the
same BIO / JSONL schema used here (`app/ml/data/skill_ner_seed.jsonl`).

### Tier 3 — Active learning loop (once the app has real users)
Log low-confidence model predictions (see `ner_inference.py`, confidence
scores) from real usage, spot-check/correct a sample weekly, add corrected
examples back into the training set, retrain periodically. This is how
accuracy compounds over time without a big upfront labeling budget.

**Target size to start seeing real gains over taxonomy-only**: ~2–3k labeled
sentences (Tier 1 bootstrap alone can produce this in an afternoon; blend in
a few hundred Tier 2 gold examples for quality).

---

## 3. Files in this build

```
backend/app/ml/
├── data/
│   └── skill_ner_seed.jsonl     # tiny hand-written seed set (format example + smoke-test data)
├── train_ner.py                 # fine-tuning script (HF Trainer)
├── evaluate_ner.py              # precision/recall/F1 via seqeval
├── ner_inference.py             # inference wrapper used by skill_extractor.py
└── model_artifacts/             # trained model + tokenizer saved here (gitignored)
```

Data format — one JSON object per line:
```json
{"tokens": ["Built", "data", "pipelines", "using", "Apache", "Airflow", "and", "dbt", "."],
 "tags":   ["O", "B-SKILL", "I-SKILL", "O", "B-SKILL", "I-SKILL", "O", "B-SKILL", "O"]}
```

`skill_ner_seed.jsonl` ships with ~20 hand-written examples so the pipeline
runs end-to-end out of the box (useful for testing the training/eval code);
**swap it for your Tier 1 + Tier 2 data before training a model you'd actually
ship.**

---

## 4. Training

```bash
cd backend
pip install transformers datasets seqeval torch accelerate --extra-index-url https://download.pytorch.org/whl/cpu
python -m app.ml.train_ner --data app/ml/data/skill_ner_seed.jsonl --epochs 8 --out app/ml/model_artifacts
```

Key hyperparameters (already set as sane defaults in `train_ner.py`, override via CLI flags):
- `learning_rate=3e-5`, `batch_size=16`, `epochs=8` for a few-thousand-sentence dataset (increase epochs for smaller sets, decrease for larger).
- 90/10 train/validation split, best checkpoint kept by validation F1.

Evaluate:
```bash
python -m app.ml.evaluate_ner --model app/ml/model_artifacts --data app/ml/data/skill_ner_seed.jsonl
```
Reports precision/recall/F1 at the entity-span level (via `seqeval`), which is
the right metric here — token-level accuracy is misleading for span extraction.

**Accuracy targets** (rule of thumb for this task with the tiered data strategy above):
- Distant-supervision-only: entity F1 ~0.65–0.72 (inherits taxonomy's blind spots)
- + a few hundred Tier 2 gold examples: F1 ~0.78–0.85
- + active-learning loop over a few months of real usage: F1 0.85+

---

## 5. Fusing NER with the taxonomy matcher

`skill_extractor.py` should merge both signals rather than picking one:

- Taxonomy hit **and** NER hit on overlapping span → high-confidence skill, keep as-is (canonical name from taxonomy).
- Taxonomy hit, no NER agreement → keep (taxonomy is precise for known terms; don't let NER veto it).
- NER hit, **not** in taxonomy → this is the valuable new signal. Keep as a skill candidate, tagged as `source: "ner"`, surfaced with the model's confidence score. Optionally auto-add high-confidence recurring novel terms to the taxonomy over time (semi-automated taxonomy growth).

This fusion logic is implemented in `ner_inference.extract_skills_ner()` +
the updated `skill_extractor.extract_skills()`.

---

## 6. Deployment notes (Cloud Run cold-start)

- Export to **ONNX** and quantize to `int8` (`optimum` library:
  `optimum-cli export onnx --model app/ml/model_artifacts --task token-classification onnx_model/`)
  — cuts a DistilBERT model from ~260MB to ~70MB and roughly halves CPU inference latency.
- Load the model once at container startup (module-level singleton, as done in
  `ner_inference.py`), not per-request.
- If cold-start latency is still a problem on a scale-to-zero Cloud Run service,
  set `min_instances=1` for the backend service so one instance stays warm.
