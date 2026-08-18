# No JD Provided Mode — Product Spec

**Status**: Draft — validated with 5 synthetic resumes (anonymized)

## Overview

When no job description is provided, the product operates in **"pure resume analysis" mode**:
evaluate the resume's structural quality (ATS) and content quality independently,
without any JD matching component. The JD match score is explicitly `null`, and the
overall score re-weights to ATS + Content only.

## Modes of Operation

### 1. Upload Resume Only (no JD)

- **ATS score**: Computed from structural flags (column layout, tables, headers/footers,
  embedded images, font issues, margins, hyperlinks, etc.)
- **Content score**: Computed from writing quality flags (weak verbs, lack of
  quantification, passive voice, grammar/spelling, readability, etc.)
- **Match score**: `null` — not applicable
- **Overall score**: Re-weighted from the default 30/30/40 formula to **ATS 50% / Content 50%**

### 2. Upload Resume + JD (normal mode)

- All three scores computed as usual
- Overall score: ATS 30% + Content 30% + JD Match 40%
- Findings from all three engines merged and prioritized

## Schema Changes (already implemented in `backend/app/models/schemas.py`)

- `match_score: MatchScore | None` — nullable, `null` when no JD provided
- `overall_score` auto-recalculates: if `match_score` is `None`, re-weights to
  ATS 50% / Content 50% regardless of configured weights
- `ResumeIntelligenceReport.summary` adapts its one-liner based on which scores
  are present (see `build_summary()` in schemas.py)

## User-Facing Behavior

### When JD is not provided:

1. **ATS Preview Pane** ("what the parser sees") is prominently displayed — this
   is the primary trust-building feature, showing users proof their content survives
   parsing intact.

2. **Content Quality metrics** surface as headline metrics:
   - Quantified bullet %
   - Weak verb count
   - Achievement/Duty ratio

3. **Top 5 Fixes** digest is generated from ATS + Content findings only, no match-
   related recommendations.

4. **Section health map** shows which required sections are present/missing, with
   explanations tailored to "no JD" context (e.g., "Summary missing — recommended
   for senior roles" rather than "not matched to JD").

5. **No disclaimer** about "AI-suggested" is needed since all findings are rule-based,
   not LLM-assisted.

### When JD IS provided:

- All existing behavior persists unchanged.
- The UI composes all three score rings + findings list as described in Phase E.

## Scoring Formula (no JD mode)

```
overall_score = round( (ats_weight * ats_score + content_weight * content_score), 1 )
where ats_weight + content_weight = 1.0, and both default to 0.5
```

The weighted formula is the same as the JD mode, just with `match_weight = 0`
and the remaining weights re-normalized.

## Tested Against

5 synthetic resumes with varying quality levels (good, medium, poor structure +
good/medium/poor content). All 5 produced differentiated ATS + Content scores
with the correct re-weighting, and the summary text adapted correctly.

## Disclaimer (not needed for no-JD mode)

Since all findings are rule-based (no LLM rewrites), no "AI-suggested — review
before use" disclaimer is shown. If the optional LLM rewrite module (Phase C.2)
is enabled later, the disclaimer would appear alongside any LLM-generated content.