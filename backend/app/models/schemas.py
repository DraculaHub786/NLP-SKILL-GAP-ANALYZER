"""API request/response contracts.

These are the source of truth for the frontend's ResumeIntelligenceReport type — keep any
change here mirrored in frontend/src/types/resumeIntelligenceReport.ts.

Two report shapes coexist:
- GapReport: the classic skill-gap report from the original matcher (match score,
  matched/missing/bonus skills, recommendations). Kept for backward compatibility.
- ResumeIntelligenceReport: the unified 3-engine report (ATS / Content / JD Match)
  that also embeds the skill-gap data so the results UI can render both.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ExtractedSkills(BaseModel):
    raw_text: str
    skills: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    resume_skills: list[str] = Field(default_factory=list)
    jd_skills: list[str] = Field(default_factory=list)
    # Client-generated random UUID used as the anonymous Redis cache key so
    # the same browser can revisit this report (GET /session/{id}) without
    # re-uploading. Never derived from identity.
    session_id: str | None = Field(default=None, max_length=64)

    @field_validator("resume_skills", "jd_skills")
    @classmethod
    def strip_and_dedupe(cls, skills: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for s in skills:
            cleaned = s.strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                out.append(cleaned)
        return out


class SkillMatch(BaseModel):
    resume_skill: str
    jd_skill: str
    similarity: float = Field(ge=0.0, le=1.0)


class Recommendation(BaseModel):
    skill: str
    importance: float = Field(default=1.0, ge=0.0)
    resources: list[str] = Field(default_factory=list)
    estimated_score_impact: str | None = Field(
        default=None,
        description="Human-readable estimate of how much adding this skill would "
        "move the overall score, e.g. '+3.2 pts to overall score if added credibly'.",
    )


# ── Legacy skill-gap report (backward compatible) ─────────────────────────────

class GapReport(BaseModel):
    match_score: float = Field(ge=0.0, le=100.0)
    matched: list[SkillMatch] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    bonus: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    summary: str = ""


# ── Resume Intelligence Report (3 engines) ────────────────────────────────────

# Individual sub-scores
class AtScore(BaseModel):
    """ATS Compatibility Score: how well the resume parses structurally."""
    score: float = Field(ge=0.0, le=100.0)
    findings: list[Finding] = Field(default_factory=list)
    format: str = Field(default="pdf")  # "pdf" or "docx"


class ContentScore(BaseModel):
    """Content Quality Score: how strong the writing is, regardless of JD."""
    score: float = Field(ge=0.0, le=100.0)
    quantified_bullet_pct: float = Field(ge=0.0, le=100.0)
    weak_verb_count: int = Field(default=0, ge=0)
    achievement_duty_ratio: float = Field(ge=0.0, le=1.0)


class MatchScore(BaseModel):
    """JD Match Score: how well resume skills match the job description."""
    score: float = Field(ge=0.0, le=100.0)
    matched_count: int = Field(default=0, ge=0)
    missing_count: int = Field(default=0, ge=0)


class EligibilityResult(BaseModel):
    """Eligibility verdict: turns the overall score + hard gates into a
    human-readable band, probability estimate, and override flag."""
    score: float = Field(ge=0.0, le=100.0)
    band: str  # "strong_fit", "good_fit", "moderate_fit", "weak_fit"
    label: str  # human-readable description of the band
    downgraded_by_hard_gate: bool = Field(
        default=False,
        description="True when the band was capped lower than the numeric score "
        "suggests, due to critical ATS failures or very low match score.",
    )
    probability_estimate: float = Field(
        ge=0.0, le=100.0,
        description="Estimated screening-pass likelihood (0–100). "
        "NOT a claim of interview/offer probability.",
    )


# A single finding/flag from any of the three engines
class Finding(BaseModel):
    category: str  # "ats", "content", "match"
    severity: str  # "critical", "major", "minor", "info"
    section: str | None = None  # which section of the resume
    message: str  # plain-English explanation
    why_it_matters: str  # why this matters for the user
    fix_suggestion: str  # concrete fix
    example_before: str  # before example (for content/rewrite flags)
    example_after: str | None = None  # after example (optional)


# The unified report model — 3 sub-scores rolled into 1 overall score
class ResumeIntelligenceReport(BaseModel):
    """Full resume intelligence report with three independent sub-scores.

    `match_score` is nullable: when no JD is provided it is None and
    `overall_score` re-weights to ATS + Content only (50/50).
    """

    ats_score: AtScore = Field(default_factory=AtScore)
    content_score: ContentScore = Field(default_factory=ContentScore)
    match_score: MatchScore | None = Field(
        default=None,
        description="Nullable: excluded when no JD is provided.",
    )
    overall_score: float = Field(ge=0.0, le=100.0)
    findings: list[Finding] = Field(default_factory=list)
    top_fixes: list[Finding] = Field(
        default_factory=list,
        description="Curated subset — the single most useful findings for quick action.",
    )
    section_summary: dict[str, str] = Field(
        default_factory=dict,
        description="e.g. {contact: 'present', experience: 'missing', education: 'present'}",
    )
    metadata: dict[str, object] = Field(
        default_factory=dict,
        description="e.g. {'word_count': 246, 'page_count': 2, 'format_issues_count': 1}",
    )
    # Skill-gap data embedded so the results UI can render the classic
    # matched/missing/bonus sections alongside the new score breakdown.
    matched: list[SkillMatch] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    bonus: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    summary: str = ""
    # Extracted plain text, returned to the browser for the "what the parser
    # sees" preview. Never persisted server-side — matches the privacy model.
    raw_text: str = ""
    # Eligibility verdict (Phase 2–3): band, probability, hard-gate flag.
    eligibility: EligibilityResult | None = Field(
        default=None,
        description="Eligibility verdict computed from the overall score + hard gates. "
        "Null only for legacy /analyze calls.",
    )
    # Transparent degradation warnings (Phase 2): surfaced to the user so they
    # know when a score was computed in degraded mode.
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings, e.g. 'Semantic matching unavailable — "
        "using exact-name matching only.' Empty when all engines ran at full capacity.",
    )


def build_summary(report: "ResumeIntelligenceReport") -> str:
    """Human-readable one-liner summarizing the report, used by the UI headline."""
    critical_flags = [f for f in report.findings if f.severity == "critical"]
    if critical_flags:
        top = critical_flags[0].message
        if ":" in top:
            top = top.split(":")[0]
        return f"{len(critical_flags)} critical issue(s) — {top[:80]}."

    if not report.match_score:
        # No JD provided — focus on ATS + Content
        ats = report.ats_score.score
        content = report.content_score.score
        return (
            f"ATS Score: {ats:.0f}/100 | Content Score: {content:.0f}/100 "
            f"— no JD match computed. (Overall: {report.overall_score:.0f}/100)"
        )

    missing = report.match_score.missing_count
    if not missing:
        return (
            f"You have all the skills this role asks for — great fit! "
            f"(Overall: {report.overall_score:.0f}/100)"
        )
    top_skill = report.recommendations[0].skill if report.recommendations else (
        report.missing[0] if report.missing else "your next skill"
    )
    return (
        f"{missing} skill{'s' if missing != 1 else ''} to close — start with "
        f"{top_skill}, which matters most for this role. "
        f"(Overall: {report.overall_score:.0f}/100)"
    )


def build_gap_summary(report: "GapReport") -> str:
    """Legacy summary for the classic skill-gap report (/analyze)."""
    if report.missing:
        top_skill = report.recommendations[0].skill if report.recommendations else report.missing[0]
        return (
            f"{len(report.missing)} skills to close — start with {top_skill}, "
            f"which matters most for this role. (Overall: {report.match_score}/100)"
        )
    if report.match_score > 0:
        return (
            f"You have all the skills this role asks for — great fit! "
            f"(Overall: {report.match_score}/100)"
        )
    return "No skills were matched — review the job description and your skills list."
