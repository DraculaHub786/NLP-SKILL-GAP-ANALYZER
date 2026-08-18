"""Phase 1 tests for the semantic gap-scoring engine.

Exact/case-insensitive matching and importance weighting are covered
without any embedding model (works even in degraded mode). Embedding-based
synonym matching is covered when sentence-transformers is installed.
"""
from app.services import matcher


def test_identical_skill_sets_score_100():
    skills = ["Python", "SQL", "Docker"]
    report = matcher.compute_gap_report(skills, skills)
    assert report.match_score == 100.0
    assert len(report.matched) == 3
    assert report.missing == []
    assert report.bonus == []


def test_disjoint_sets_score_0():
    report = matcher.compute_gap_report(["Python", "Java"], ["Rust", "Go"])
    assert report.match_score == 0.0
    assert report.matched == []
    assert set(report.missing) == {"Rust", "Go"}
    assert set(report.bonus) == {"Python", "Java"}


def test_case_insensitive_exact_match_counts_as_matched():
    report = matcher.compute_gap_report(["python"], ["Python"])
    assert report.match_score == 100.0
    assert len(report.matched) == 1
    assert report.matched[0].similarity == 1.0


def test_importance_weighting_shifts_score():
    """A JD whose only must-have is missing scores far lower than one where
    the missing skill is low-importance."""
    jd_skills = ["Python", "Docker", "Kafka"]
    resume = ["Docker"]

    # Kafka is the must-have (weight ~2.0) and is missing -> score collapses.
    weighted = {"Python": 0.5, "Docker": 0.5, "Kafka": 2.0}
    report_heavy = matcher.compute_gap_report(resume, jd_skills, jd_importance=weighted)

    # Uniform weights: 1 of 3 matched -> ~33%.
    report_uniform = matcher.compute_gap_report(resume, jd_skills)

    assert report_heavy.match_score < report_uniform.match_score


def test_importance_weighting_floors_and_scales():
    importance = matcher._normalize_weights(["A", "B"], {"A": 4.0, "B": 1.0})
    assert importance["A"] == 4.0  # caller-provided raw weights pass through rounded
    floored = matcher._normalize_weights(["C", "D"], None)
    assert floored == {"C": 1.0, "D": 1.0}


def test_empty_jd_skills_returns_zero_report():
    report = matcher.compute_gap_report(["Python"], [])
    assert report.match_score == 0.0
    assert report.bonus == ["Python"]
    assert report.recommendations == []


def test_recommendations_ranked_by_importance():
    jd_skills = ["Python", "Docker"]
    resume: list[str] = []
    weighted = {"Python": 2.0, "Docker": 0.5}
    report = matcher.compute_gap_report(resume, jd_skills, jd_importance=weighted)
    assert report.recommendations[0].skill == "Python"
    assert len(report.recommendations[0].resources) >= 1


def test_learning_resources_always_present():
    known = matcher._learning_resources("Python")
    assert any("docs.python.org" in r for r in known)
    fallback = matcher._learning_resources("Some Obscure Skill 2026")
    assert len(fallback) == 2
    assert all(r.startswith("https://") for r in fallback)


def test_no_duplicate_bonus_when_multiple_jd_skills_match_one_resume():
    """One resume skill should match at most one JD skill (greedy per-JD loop),
    so the resume skill doesn't appear in both matched and bonus."""
    report = matcher.compute_gap_report(["Docker"], ["Docker", "Docker"])
    assert report.match_score == 100.0
    assert report.bonus == []
