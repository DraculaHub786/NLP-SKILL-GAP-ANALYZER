"""API request/response contracts.

These are the source of truth for the frontend's GapReport type — keep any
change here mirrored in frontend/src/types/gapReport.ts.
"""
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


class GapReport(BaseModel):
    match_score: float = Field(ge=0.0, le=100.0)
    matched: list[SkillMatch] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    bonus: list[str] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    summary: str = ""


def build_summary(report: "GapReport") -> str:
    """Human-readable one-liner summarizing the gap, used by the UI headline."""
    if not report.missing:
        return "You have all the skills this role asks for — great fit!"
    top = report.recommendations[0].skill if report.recommendations else report.missing[0]
    return (
        f"{len(report.missing)} skills to close — start with {top}, "
        f"which matters most for this role."
    )
