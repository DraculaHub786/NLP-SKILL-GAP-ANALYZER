/**
 * Mirrors backend/app/models/schemas.py (ResumeIntelligenceReport + Finding).
 * The backend schema is the source of truth — keep changes mirrored in both.
 */

export type FindingCategory = "ats" | "content" | "match";
export type FindingSeverity = "critical" | "major" | "minor" | "info";

export interface Finding {
  category: FindingCategory;
  severity: FindingSeverity;
  section: string | null;
  message: string;
  why_it_matters: string;
  fix_suggestion: string;
  example_before: string;
  example_after: string | null;
}

export interface AtScore {
  score: number;
  findings: Finding[];
  format: string;
}

export interface ContentScore {
  score: number;
  quantified_bullet_pct: number;
  weak_verb_count: number;
  achievement_duty_ratio: number;
}

export interface MatchScore {
  score: number;
  matched_count: number;
  missing_count: number;
}

export interface SkillMatch {
  resume_skill: string;
  jd_skill: string;
  similarity: number;
}

export interface RecommendedSkill {
  skill: string;
  importance: number;
  resources: string[];
  estimated_score_impact: string | null;
}

export interface EligibilityResult {
  score: number;
  band: string;
  label: string;
  downgraded_by_hard_gate: boolean;
  probability_estimate: number;
}

export interface ScoreBreakdown {
  weights: Record<string, number>;
  ats_weight: number;
  content_weight: number;
  match_weight: number;
  ats_contribution: number;
  content_contribution: number;
  match_contribution: number | null;
}

export interface Metadata {
  word_count?: number;
  page_count?: number;
  format_issues_count?: number;
  no_jd_mode?: boolean;
  score_breakdown?: ScoreBreakdown;
  [key: string]: unknown;
}

export interface ResumeIntelligenceReport {
  ats_score: AtScore;
  content_score: ContentScore;
  match_score: MatchScore | null;
  overall_score: number;
  findings: Finding[];
  top_fixes: Finding[];
  section_summary: Record<string, string>;
  metadata: Metadata;
  matched: SkillMatch[];
  missing: string[];
  bonus: string[];
  recommendations: RecommendedSkill[];
  summary: string;
  raw_text: string;
  eligibility: EligibilityResult | null;
  warnings: string[];
}

export interface ExtractedSkills {
  raw_text: string;
  skills: string[];
}
