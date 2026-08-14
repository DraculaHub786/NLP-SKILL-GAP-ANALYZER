import json
import uuid

import redis
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.models.schemas import AnalyzeRequest, ExtractedSkills, GapReport
from app.services.matcher import compute_gap_report
from app.services.resume_parser import parse_resume
from app.services.skill_extractor import extract_skills

router = APIRouter(prefix="/api/v1")
_redis = redis.from_url(settings.redis_url, decode_responses=True)


@router.post("/parse/resume", response_model=ExtractedSkills)
async def parse_resume_endpoint(file: UploadFile = File(...)):
    file_bytes = await file.read()  # in-memory only, never persisted to disk
    try:
        text = parse_resume(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExtractedSkills(raw_text=text, skills=extract_skills(text))


@router.post("/parse/jd", response_model=ExtractedSkills)
async def parse_jd_endpoint(text: str = Form(...)):
    return ExtractedSkills(raw_text=text, skills=extract_skills(text))


@router.post("/analyze", response_model=GapReport)
async def analyze_endpoint(payload: AnalyzeRequest):
    report = compute_gap_report(payload.resume_skills, payload.jd_skills)

    session_id = str(uuid.uuid4())
    _redis.setex(f"session:{session_id}", settings.session_ttl_seconds, report.model_dump_json())

    return report


@router.get("/session/{session_id}", response_model=GapReport)
async def get_session(session_id: str):
    cached = _redis.get(f"session:{session_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Session expired or not found.")
    return GapReport(**json.loads(cached))


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    _redis.delete(f"session:{session_id}")
    return {"deleted": True}


@router.get("/health")
async def health():
    return {"status": "ok"}
