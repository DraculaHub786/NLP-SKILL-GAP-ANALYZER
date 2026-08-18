"""Versioned API routes — thin HTTP orchestration over the services.

No NLP logic lives here. Every external call (file parse, model inference,
Redis) is wrapped with explicit error handling; raw exceptions never reach
the client as unlabeled 500s.
"""
import json
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import (
    AnalyzeRequest,
    ExtractedSkills,
    GapReport,
    MatchScore,
    ResumeIntelligenceReport,
    build_gap_summary,
    build_summary,
)
from app.services.ats_structure_checker import run_all_ats_structure_checks
from app.services.content_quality_analyzer import analyze_content
from app.services.matcher import _get_model as _get_embedding_model, compute_gap_report
from app.services.recommendation_engine import (
    generate_eligibility_recommendations,
    merge_findings,
    top_fixes,
)
from app.services.resume_parser import parse_resume
from app.services.scoring_engine import apply_report_scores, compute_eligibility
from app.services.section_detector import run_all_section_checks
from app.services.skill_extractor import _get_nlp as _get_spacy, extract_skills
from app.utils.logging import get_logger
from app.utils.redis_cache import (
    cache_report_json,
    delete_session,
    get_report_json,
)

router = APIRouter(prefix="/api/v1")
logger = get_logger(__name__)


# ── Text helpers for the unified analyzer ──────────────────────────────────────

_SECTION_HEADER_LIKE = re.compile(r"^(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z][A-Z\s]{2,})$")


def _extract_section_headers(text: str) -> list[str]:
    """Heuristic: short, mostly-title-case or all-caps standalone lines are
    candidate section headers fed to the section detector's alias resolution."""
    headers: list[str] = []
    for line in text.splitlines():
        stripped = line.strip().rstrip(":").strip()  # strip trailing colon first
        if not stripped or len(stripped) > 40:
            continue
        if any(ch in stripped for ch in ".,;!?•"):  # colon removed from exclusion set
            continue
        if _SECTION_HEADER_LIKE.match(stripped):
            headers.append(stripped)
    return headers[:40]


def _extract_bullet_starts(text: str) -> list[str]:
    """Returns the first line of each bullet (lines starting with •, -, or *),
    matching the formatting checker's bullet_starts parameter."""
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("•") or stripped.startswith("-") or stripped.startswith("*"):
            bullets.append(stripped)
    return bullets[:200]


def _section_summary(section_result: dict) -> dict[str, str]:
    """Turns the section detector's classified map into the report's
    section_summary ({contact: 'present'|'missing', ...})."""
    classified = section_result.get("classified", {})
    summary: dict[str, str] = {}
    for canonical, raw in classified.items():
        if canonical not in ("contact", "summary", "skills", "experience", "education", "certifications"):
            continue
        summary[canonical] = "present" if raw else "missing"
    return summary


@router.post("/parse/resume", response_model=ExtractedSkills)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    file_bytes = await file.read()  # in-memory only, never persisted to disk
    try:
        text = parse_resume(file.filename or "", file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ExtractedSkills(raw_text=text, skills=extract_skills(text))


@router.post("/parse/jd", response_model=ExtractedSkills)
async def parse_jd_endpoint(text: str = Form(...)):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Job description text is empty.")
    return ExtractedSkills(raw_text=text, skills=extract_skills(text))


@router.post("/analyze", response_model=GapReport)
async def analyze_endpoint(payload: AnalyzeRequest):
    if not payload.jd_skills:
        raise HTTPException(status_code=400, detail="No skills found in the job description.")

    report = compute_gap_report(payload.resume_skills, payload.jd_skills)
    report.summary = build_gap_summary(report)

    # Persist only the anonymized report JSON (never raw text) under the
    # client-provided session id (or a fresh one) with a 48h TTL. Returns 200
    # with the report even if Redis is down — caching is best-effort by design.
    try:
        cache_report_json(report.model_dump_json(), session_id=payload.session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return report


@router.get("/session/{session_id}", response_model=GapReport)
async def get_session(session_id: str):
    cached = get_report_json(session_id)
    if cached is None:
        raise HTTPException(status_code=404, detail="Session expired or not found.")
    return GapReport(**json.loads(cached))


@router.delete("/session/{session_id}")
async def delete_session_endpoint(session_id: str):
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session expired or not found.")
    return {"deleted": True}


@router.post("/analyze/resume", response_model=ResumeIntelligenceReport)
async def analyze_resume_endpoint(
    file: UploadFile = File(...),
    jd_text: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
):
    """Runs all three engines (ATS / Content / JD Match) on a resume upload.

    - file: the resume PDF/DOCX (parsed in-memory, never persisted)
    - jd_text: optional job description; when omitted, match_score is None and
      the overall score re-weights to ATS + Content only (50/50).
    - session_id: optional client-generated UUID for the anonymous Redis cache.
    """
    file_bytes = await file.read()
    try:
        resume_text = parse_resume(file.filename or "", file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    resume_skills = extract_skills(resume_text)

    # ── ATS engine ──────────────────────────────────────────────────────────
    ats = run_all_ats_structure_checks(
        filename=file.filename or "",
        extracted_text=resume_text,
        page_count=1,
    )
    ats.findings = [f for f in ats.findings if f.severity != "info"]

    # ── Section & formatting engines — their findings fold into the report
    # (contact/section issues live under the ats category).
    section_result = run_all_section_checks(
        raw_headers=_extract_section_headers(resume_text),
        profile_level="experienced",
        extract_contact_from_text=resume_text,
    )
    ats.findings += section_result["missing"]
    ats.findings += section_result["ordering"]
    ats.findings += section_result["duplicates"]
    ats.findings += section_result["contact_validation"]

    from app.services.formatting_consistency_checker import run_all_formatting_checks

    formatting = run_all_formatting_checks(
        text=resume_text,
        bullet_starts=_extract_bullet_starts(resume_text),
    )
    if formatting["format_inconsistency"]:
        ats.findings.append(formatting["format_inconsistency"])
    ats.findings += formatting["employment_gaps"]
    ats.findings += formatting["overlapping_dates"]
    ats.findings += formatting["chrono_order"]
    ats.findings += formatting["bullet_consistency"]

    # ── Content engine ──────────────────────────────────────────────────────
    content_score, content_findings = analyze_content(
        _extract_bullet_starts(resume_text),
        current_role_index=None,
    )

    # ── Match engine (only when a JD is provided) ───────────────────────────
    gap: GapReport | None = None
    match_score_model: MatchScore | None = None
    if jd_text and jd_text.strip():
        jd_skills = extract_skills(jd_text)
        gap = compute_gap_report(resume_skills, jd_skills)
        match_score_model = MatchScore(
            score=gap.match_score,
            matched_count=len(gap.matched),
            missing_count=len(gap.missing),
        )

    # ── Unified scoring + recommendations ───────────────────────────────────
    merged = merge_findings(ats.findings, content_findings)
    report = ResumeIntelligenceReport(
        ats_score=ats,
        content_score=content_score,
        match_score=match_score_model,
        overall_score=0.0,
        findings=merged,
        top_fixes=top_fixes(merged),
        section_summary=_section_summary(section_result),
        metadata={"word_count": len(resume_text.split()), "format_issues_count": len(ats.findings)},
        summary="",
        raw_text=resume_text[:20000],
    )
    apply_report_scores(report, gap=gap)

    # ── Eligibility verdict (Phase 3) ──────────────────────────────────────
    critical_count = sum(1 for f in ats.findings if f.severity == "critical")
    report.eligibility = compute_eligibility(
        overall_score=report.overall_score,
        match=report.match_score,
        critical_ats_findings=critical_count,
    )

    # ── Eligibility-tied recommendations (Phase 3) ─────────────────────────
    if gap:
        eligibility_recs = generate_eligibility_recommendations(gap)
        if eligibility_recs:
            report.recommendations = eligibility_recs

    # ── Warnings: transparent degradation (Phase 2) ────────────────────────
    warnings: list[str] = []
    if _get_spacy() is None:
        warnings.append(
            "AI-based skill extraction unavailable — using keyword taxonomy only. "
            "Some skills may not be detected."
        )
    if _get_embedding_model() is None:
        warnings.append(
            "Semantic skill matching unavailable — using exact-name matching only, "
            "which may miss synonyms."
        )
    report.warnings = warnings

    report.summary = build_summary(report)

    # ── Cache (best-effort, never block the response) ──────────────────────
    try:
        cache_report_json(report.model_dump_json(), session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return report


@router.get("/health")
async def health():
    return {"status": "ok"}
