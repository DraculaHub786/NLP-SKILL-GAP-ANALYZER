"""Versioned API routes — thin HTTP orchestration over the services.

No NLP logic lives here. Every external call (file parse, model inference,
Redis) is wrapped with explicit error handling; raw exceptions never reach
the client as unlabeled 500s.
"""
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schemas import (
    AnalyzeRequest,
    ExtractedSkills,
    GapReport,
    build_summary,
)
from app.services.matcher import compute_gap_report
from app.services.resume_parser import parse_resume
from app.services.skill_extractor import extract_skills
from app.utils.logging import get_logger
from app.utils.redis_cache import (
    cache_report_json,
    delete_session,
    get_report_json,
)

router = APIRouter(prefix="/api/v1")
logger = get_logger(__name__)


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
    report.summary = build_summary(report)

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


@router.get("/health")
async def health():
    return {"status": "ok"}
