"""Semantic skill matching between resume skills and JD skills.

Uses sentence embeddings so paraphrased/synonymous skills still match
(e.g. 'Data Visualization' ~ 'Dashboarding'), then computes an
importance-weighted gap score.
"""
from sentence_transformers import SentenceTransformer, util

from app.core.config import settings
from app.models.schemas import GapReport, Recommendation, SkillMatch

_model = SentenceTransformer(settings.embedding_model)


def compute_gap_report(
    resume_skills: list[str],
    jd_skills: list[str],
    jd_importance: dict[str, float] | None = None,
) -> GapReport:
    if not jd_skills:
        return GapReport(match_score=0.0, matched=[], missing=[], bonus=resume_skills, recommendations=[])

    jd_importance = jd_importance or {s: 1.0 for s in jd_skills}

    resume_emb = _model.encode(resume_skills, convert_to_tensor=True) if resume_skills else None
    jd_emb = _model.encode(jd_skills, convert_to_tensor=True)

    matched: list[SkillMatch] = []
    missing: list[str] = []
    matched_resume_idx: set[int] = set()

    for j_idx, jd_skill in enumerate(jd_skills):
        best_score, best_r_idx = 0.0, -1
        if resume_emb is not None:
            sims = util.cos_sim(jd_emb[j_idx], resume_emb)[0]
            best_r_idx = int(sims.argmax())
            best_score = float(sims[best_r_idx])

        if best_score >= settings.skill_match_threshold:
            matched.append(
                SkillMatch(
                    resume_skill=resume_skills[best_r_idx],
                    jd_skill=jd_skill,
                    similarity=round(best_score, 3),
                )
            )
            matched_resume_idx.add(best_r_idx)
        else:
            missing.append(jd_skill)

    bonus = [s for i, s in enumerate(resume_skills) if i not in matched_resume_idx]

    total_weight = sum(jd_importance.get(s, 1.0) for s in jd_skills)
    matched_weight = sum(jd_importance.get(m.jd_skill, 1.0) for m in matched)
    match_score = round((matched_weight / total_weight) * 100, 1) if total_weight else 0.0

    recommendations = [
        Recommendation(
            skill=skill,
            importance=round(jd_importance.get(skill, 1.0), 2),
            resources=[f"https://www.google.com/search?q=learn+{skill.replace(' ', '+')}"],
        )
        for skill in sorted(missing, key=lambda s: -jd_importance.get(s, 1.0))
    ]

    return GapReport(
        match_score=match_score,
        matched=matched,
        missing=missing,
        bonus=bonus,
        recommendations=recommendations,
    )
