"""Unified Scoring — 3 sub-scores rolled into 1 overall score.

Score explainability is a core requirement: every sub-score returns not just a
number but a breakdown of what contributed to it, so the UI can show
"72/100 — here's why" instead of a bare number users won't trust.

Weights are configuration, not hardcoded constants:
- With JD:  ATS 30% / Content 30% / Match 40%  (DEFAULT_WEIGHTS)
- No JD:    ATS 50% / Content 50%              (NO_JD_WEIGHTS, match omitted)

Error contract: pure functions — no I/O, never raise.
"""
from __future__ import annotations

import math

from app.models.schemas import (
    AtScore,
    ContentScore,
    EligibilityResult,
    Finding,
    GapReport,
    MatchScore,
    ResumeIntelligenceReport,
)

# Configurable, not hardcoded: tune after testing against real resumes.
DEFAULT_WEIGHTS = {"ats": 0.3, "content": 0.3, "match": 0.4}
NO_JD_WEIGHTS = {"ats": 0.5, "content": 0.5, "match": 0.0}

# Penalties per severity for the ATS sub-score (start at 100, subtract).
PENALTIES = {"critical": 15, "major": 8, "minor": 3, "info": 1}


def _penalty(bucket: list[Finding]) -> float:
    return round(sum(PENALTIES.get(f.severity, 0) for f in bucket), 1)


def score_ats(findings: list[Finding], format: str = "pdf") -> tuple[float, dict[str, object]]:
    """ATS sub-score: start at 100, subtract weighted penalties per flag.

    Returns (score, breakdown) so the UI can explain the number.
    """
    by_severity = {
        "critical": [f for f in findings if f.severity == "critical"],
        "major": [f for f in findings if f.severity == "major"],
        "minor": [f for f in findings if f.severity == "minor"],
        "info": [f for f in findings if f.severity == "info"],
    }
    penalty = sum(_penalty(bucket) for bucket in by_severity.values())
    score = max(0.0, round(100.0 - penalty, 1))
    breakdown = {
        "start": 100.0,
        "penalty": penalty,
        "critical_count": len(by_severity["critical"]),
        "major_count": len(by_severity["major"]),
        "minor_count": len(by_severity["minor"]),
        "info_count": len(by_severity["info"]),
        "format": format,
    }
    return score, breakdown


def score_content(content: ContentScore) -> tuple[float, dict[str, object]]:
    """Content sub-score: the analyzer's score plus a human-readable breakdown.

    The analyzer already computed the number; this function makes the reasons
    explicit (quantified-bullet %, achievement ratio, weak verbs).
    """
    breakdown: dict[str, object] = {
        "quantified_bullet_pct": content.quantified_bullet_pct,
        "achievement_duty_ratio": content.achievement_duty_ratio,
        "weak_verb_count": content.weak_verb_count,
    }
    return content.score, breakdown


def score_match(report: GapReport) -> tuple[float, dict[str, object]]:
    """Match sub-score: derived from the skill-gap report."""
    breakdown: dict[str, object] = {
        "matched_count": len(report.matched),
        "missing_count": len(report.missing),
        "bonus_count": len(report.bonus),
        "recommendation_count": len(report.recommendations),
    }
    return report.match_score, breakdown


def score_overall(
    ats: float,
    content: float,
    match: float | None,
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, object]]:
    """Weighted rollup of the three sub-scores.

    When `match` is None (no JD provided), re-weights to ATS + Content only
    (50/50) — an explicit branch, not an accident.
    """
    w = dict(weights or DEFAULT_WEIGHTS)

    # Reject explicitly-invalid weight sets before the no-JD substitution so a
    # caller passing all-zero weights gets the error branch, not a silent 50/50.
    if sum(w.values()) <= 0:
        return 0.0, {"weights": w, "error": "no positive weights"}

    if match is None:
        w = dict(NO_JD_WEIGHTS)

    total_w = w.get("ats", 0.0) + w.get("content", 0.0) + w.get("match", 0.0)
    if total_w <= 0:
        return 0.0, {"weights": w, "error": "no positive weights"}

    weighted = w.get("ats", 0.0) * ats + w.get("content", 0.0) * content
    if match is not None:
        weighted += w.get("match", 0.0) * match

    overall = round(weighted / total_w, 1)
    breakdown = {
        "weights": w,
        "ats_weight": w.get("ats", 0.0) / total_w,
        "content_weight": w.get("content", 0.0) / total_w,
        "match_weight": w.get("match", 0.0) / total_w if match is not None else 0.0,
        "ats_contribution": round(w.get("ats", 0.0) * ats / total_w, 1),
        "content_contribution": round(w.get("content", 0.0) * content / total_w, 1),
        "match_contribution": (
            round(w.get("match", 0.0) * match / total_w, 1) if match is not None else None
        ),
    }
    return overall, breakdown


def apply_report_scores(
    report: ResumeIntelligenceReport,
    gap: GapReport | None = None,
    weights: dict[str, float] | None = None,
) -> ResumeIntelligenceReport:
    """Populates `overall_score` on a ResumeIntelligenceReport from its
    sub-scores, plus score-breakdown metadata. Mutates and returns the report.

    If `match_score` is None (no JD mode), re-weights to ATS + Content only.
    """
    ats = report.ats_score.score
    content = report.content_score.score
    match = report.match_score.score if report.match_score else None

    overall, breakdown = score_overall(ats, content, match, weights)

    metadata = dict(report.metadata)
    metadata["score_breakdown"] = breakdown
    if breakdown.get("match_contribution") is None:
        metadata["no_jd_mode"] = True

    report.overall_score = overall
    report.metadata = metadata

    if gap is not None:
        # Keep the embedded skill-gap data and match sub-score in sync.
        report.matched = gap.matched
        report.missing = gap.missing
        report.bonus = gap.bonus
        report.recommendations = gap.recommendations
        if report.match_score is None:
            report.match_score = MatchScore(
                score=gap.match_score,
                matched_count=len(gap.matched),
                missing_count=len(gap.missing),
            )

    return report


def ats_from_findings(findings: list[Finding], format: str = "pdf") -> AtScore:
    """Builds an AtScore object from a flat finding list."""
    score, _breakdown = score_ats(findings, format=format)
    return AtScore(score=score, findings=findings, format=format)


# ── Eligibility engine (Phase 3) ─────────────────────────────────────────────

ELIGIBILITY_BANDS = [
    (85, "strong_fit", "Strong fit — apply with confidence"),
    (70, "good_fit", "Good fit — a few gaps to close before applying"),
    (55, "moderate_fit", "Moderate fit — meaningful gaps, worth addressing first"),
    (0, "weak_fit", "Weak fit — significant reskilling needed for this role"),
]


def _score_to_probability(overall_score: float, critical_ats_findings: int) -> float:
    """A calibrated 'probability of passing initial screening' estimate.

    NOT a claim of interview/offer probability — those depend on market,
    competition, and recruiter factors this tool cannot see. Logistic squashing
    keeps the estimate bounded and avoids false precision at the extremes.
    """
    x = (overall_score - 60) / 12  # centered around the pass line
    p = 1 / (1 + math.exp(-x))
    penalty = min(0.25, critical_ats_findings * 0.08)
    return round(max(0.02, min(0.97, p - penalty)) * 100, 1)


def compute_eligibility(
    overall_score: float,
    match: MatchScore | None,
    critical_ats_findings: int,
) -> EligibilityResult:
    """Turns the overall score + hard gates into an eligibility verdict.

    Two things can override a numerically-decent score:
    - Any *critical* ATS finding (e.g. unparseable file, no skills section)
      caps the band at 'moderate_fit' even if the number is high, because a
      parser that can't read the resume will never surface it to a recruiter.
    - If a JD was provided and match_score < 40, cap at 'weak_fit' — content
      and formatting can't compensate for a fundamental skill mismatch.
    """
    verdict_key = "weak_fit"
    verdict_label = ELIGIBILITY_BANDS[-1][2]

    for threshold, key, label in ELIGIBILITY_BANDS:
        if overall_score >= threshold:
            verdict_key, verdict_label = key, label
            break

    # Hard gates (never let bad fundamentals hide behind a decent average)
    downgraded = False
    if critical_ats_findings > 0 and verdict_key in ("strong_fit", "good_fit"):
        verdict_key, verdict_label = "moderate_fit", ELIGIBILITY_BANDS[2][2]
        downgraded = True
    if match is not None and match.score < 40 and verdict_key != "weak_fit":
        verdict_key, verdict_label = "weak_fit", ELIGIBILITY_BANDS[-1][2]
        downgraded = True

    return EligibilityResult(
        score=overall_score,
        band=verdict_key,
        label=verdict_label,
        downgraded_by_hard_gate=downgraded,
        probability_estimate=_score_to_probability(overall_score, critical_ats_findings),
    )
