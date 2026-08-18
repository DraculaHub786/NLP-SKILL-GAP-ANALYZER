/**
 * Mirrors backend/app/models/schemas.py (GapReport, SkillMatch, RecommendedSkill).
 * The backend schema is the source of truth — keep changes mirrored in both.
 */

export interface SkillMatch {
  resume_skill: string;
  jd_skill: string;
  similarity: number;
}

export interface RecommendedSkill {
  skill: string;
  importance: number;
  resources: string[];
}

export interface GapReport {
  match_score: number;
  matched: SkillMatch[];
  missing: string[];
  bonus: string[];
  recommendations: RecommendedSkill[];
  summary: string;
}

export interface ExtractedSkills {
  raw_text: string;
  skills: string[];
}
