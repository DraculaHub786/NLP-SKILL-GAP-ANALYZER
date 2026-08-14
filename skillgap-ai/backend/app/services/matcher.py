"""Semantic skill matching between resume skills and JD skills.

Uses sentence embeddings so paraphrased/synonymous skills still match
(e.g. 'Data Visualization' ~ 'Dashboarding'), then computes an
importance-weighted gap score.

Importance weights come from the JD: how often a skill is mentioned plus a
boost for skills appearing in a Requirements/Must-have section (parsed by the
JD parser). Weights are normalized within this module, so callers can pass
raw mention counts.
"""
from app.core.config import settings
from app.models.schemas import GapReport, Recommendation, SkillMatch
from app.utils.logging import get_logger

logger = get_logger(__name__)

_model = None


def _get_model():
    """Lazily loads the embedding model once; returns None if unavailable
    (degrades to exact-string matching when sentence-transformers isn't
    installed). Failed loads are cached so we don't retry per request."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(settings.embedding_model)
        except Exception as exc:
            logger.error("embedding_model_load_failed", error=str(exc))
            _model = False  # sentinel: load failed, don't retry
    # Never hand a non-model value back to callers, even if a load failed.
    return _model if not isinstance(_model, bool) else None


def _normalize_weights(
    jd_skills: list[str], raw_importance: dict[str, float] | None
) -> dict[str, float]:
    """Maps per-skill importance to rounded floats so the weighted score stays
    interpretable: default 1.0, must-have ~2.0, nice-to-have ~0.6."""
    if raw_importance:
        return {s: round(raw_importance.get(s, 1.0), 2) for s in jd_skills}
    return {s: 1.0 for s in jd_skills}


def compute_gap_report(
    resume_skills: list[str],
    jd_skills: list[str],
    jd_importance: dict[str, float] | None = None,
) -> GapReport:
    if not jd_skills:
        return GapReport(
            match_score=0.0,
            matched=[],
            missing=[],
            bonus=resume_skills,
            recommendations=[],
        )

    importance = _normalize_weights(jd_skills, jd_importance)

    model = _get_model()
    resume_emb = None
    jd_emb = None
    if model is not None:
        resume_emb = (
            model.encode(resume_skills, convert_to_tensor=True) if resume_skills else None
        )
        jd_emb = model.encode(jd_skills, convert_to_tensor=True)

    matched: list[SkillMatch] = []
    missing: list[str] = []
    matched_resume_lower: set[str] = set()

    for j_idx, jd_skill in enumerate(jd_skills):
        best_score = 0.0
        best_r_idx = -1

        if resume_skills:
            lowered = [s.lower() for s in resume_skills]
            # Exact or near-exact (case-insensitive) match always wins.
            if jd_skill.lower() in lowered:
                best_r_idx = lowered.index(jd_skill.lower())
                best_score = 1.0
            elif model is not None and jd_emb is not None and resume_emb is not None:
                sims = jd_emb[j_idx] @ resume_emb.T
                best_r_idx = int(sims.argmax().item())
                best_score = float(sims[best_r_idx].item())

        if best_score >= settings.skill_match_threshold:
            matched.append(
                SkillMatch(
                    resume_skill=resume_skills[best_r_idx],
                    jd_skill=jd_skill,
                    similarity=round(best_score, 3),
                )
            )
            matched_resume_lower.add(resume_skills[best_r_idx].lower())
        else:
            missing.append(jd_skill)

    bonus = [s for s in resume_skills if s.lower() not in matched_resume_lower]

    total_weight = sum(importance.get(s, 1.0) for s in jd_skills)
    matched_weight = sum(importance.get(m.jd_skill, 1.0) for m in matched)
    match_score = round((matched_weight / total_weight) * 100, 1) if total_weight else 0.0

    recommendations = [
        Recommendation(
            skill=skill,
            importance=round(importance.get(skill, 1.0), 2),
            resources=_learning_resources(skill),
        )
        for skill in sorted(missing, key=lambda s: -importance.get(s, 1.0))
    ]

    return GapReport(
        match_score=match_score,
        matched=matched,
        missing=missing,
        bonus=bonus,
        recommendations=recommendations,
    )


_RESOURCE_BASES = {
    "Python": ("https://docs.python.org/3/tutorial/", "https://realpython.com/"),
    "Machine Learning": ("https://www.coursera.org/learn/machine-learning", "https://scikit-learn.org/stable/tutorial/index.html"),
    "Deep Learning": ("https://www.coursera.org/specializations/deep-learning", "https://pytorch.org/tutorials/"),
    "Natural Language Processing": ("https://www.nltk.org/book/", "https://huggingface.co/learn/nlp-course"),
    "React": ("https://react.dev/learn", "https://www.freecodecamp.org/learn/front-end-development-libraries/"),
    "JavaScript": ("https://developer.mozilla.org/en-US/docs/Web/JavaScript", "https://javascript.info/"),
    "SQL": ("https://www.w3schools.com/sql/", "https://sqlzoo.net/"),
    "Docker": ("https://docs.docker.com/get-started/", "https://www.youtube.com/watch?v=3c-iBn72dCk"),
    "Kubernetes": ("https://kubernetes.io/docs/tutorials/", "https://www.freecodecamp.org/news/learn-kubernetes-in-one-video/"),
    "AWS": ("https://aws.amazon.com/training/", "https://www.youtube.com/watch?v=ulprqHHWlng"),
    "Data Visualization": ("https://www.tableau.com/learn", "https://matplotlib.org/stable/tutorials/"),
    "REST API": ("https://restfulapi.net/", "https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django/Web_application_security"),
    "Statistics": ("https://www.khanacademy.org/math/statistics-probability", "https://openstax.org/details/books/introductory-statistics"),
    "Large Language Models": ("https://www.deeplearning.ai/courses/generative-ai-with-llms/", "https://huggingface.co/learn/llm-course"),
    "Prompt Engineering": ("https://www.promptingguide.ai/", "https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/"),
    "GraphQL": ("https://graphql.org/learn/", "https://www.howtographql.com/"),
    "TypeScript": ("https://www.typescriptlang.org/docs/", "https://www.typescriptlang.org/play"),
    "Git": ("https://git-scm.com/book/en/v2", "https://learngitbranching.js.org/"),
    "Pandas": ("https://pandas.pydata.org/docs/getting_started/index.html", "https://www.kaggle.com/learn/pandas"),
    "Django": ("https://docs.djangoproject.com/en/5.0/intro/tutorial01/", "https://www.djangoproject.com/start/"),
    "Flask": ("https://flask.palletsprojects.com/en/3.0.x/tutorial/", "https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world"),
    "PostgreSQL": ("https://www.postgresqltutorial.com/", "https://www.freecodecamp.org/news/learn-postgresql-on-your-mac/"),
    "MongoDB": ("https://university.mongodb.com/", "https://www.youtube.com/watch?v=ofme2o29ngU"),
    "Redis": ("https://try.redis.io/", "https://redis.io/docs/"),
    "System Design": ("https://github.com/donnemartin/system-design-primer", "https://www.educative.io/courses/grokking-the-system-design-interview"),
    "Algorithms": ("https://www.coursera.org/learn/algorithms-part1", "https://www.edx.org/learn/algorithms"),
    "Cybersecurity": ("https://www.cybrary.it/", "https://www.coursera.org/specializations/intro-cyber-security"),
    "Cloud Computing": ("https://www.coursera.org/specializations/cloud-computing", "https://aws.amazon.com/training/"),
}


def _learning_resources(skill: str) -> list[str]:
    """Returns curated resources for known high-value skills, else a
    targeted web search — so recommendations always have a usable link."""
    if skill in _RESOURCE_BASES:
        return list(_RESOURCE_BASES[skill])
    search = skill.replace(" ", "+")
    return [
        f"https://www.google.com/search?q=learn+{search}",
        f"https://www.youtube.com/results?search_query={search}",
    ]
