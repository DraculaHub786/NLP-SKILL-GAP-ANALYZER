from pydantic import BaseModel


class ExtractedSkills(BaseModel):
    raw_text: str
    skills: list[str]


class AnalyzeRequest(BaseModel):
    resume_skills: list[str]
    jd_skills: list[str]


class SkillMatch(BaseModel):
    resume_skill: str
    jd_skill: str
    similarity: float


class Recommendation(BaseModel):
    skill: str
    importance: float
    resources: list[str]


class GapReport(BaseModel):
    match_score: float
    matched: list[SkillMatch]
    missing: list[str]
    bonus: list[str]
    recommendations: list[Recommendation]
