"""Phase 2 tests: Gap Engine.

Verifies:
- compute_gap_score is deterministic for fixed inputs
- Severity bucketing works (critical/high/medium/low)
- compute_gaps produces deterministic, ordered output
"""
import pytest

from app.analysis import gap_engine


class TestGapScore:
    def test_no_gap(self):
        """Required == candidate -> gap 0."""
        score = gap_engine.compute_gap_score(
            required_proficiency="advanced", candidate_proficiency="advanced"
        )
        assert score == 0.0

    def test_max_gap(self):
        """Required expert, candidate beginner -> high gap."""
        score = gap_engine.compute_gap_score(
            required_proficiency="expert", candidate_proficiency="beginner"
        )
        assert score > 50.0

    def test_medium_gap(self):
        """Required advanced, candidate intermediate -> medium gap."""
        score = gap_engine.compute_gap_score(
            required_proficiency="advanced", candidate_proficiency="intermediate"
        )
        assert 0.0 < score < 100.0

    def test_importance_raises_score(self):
        low_imp = gap_engine.compute_gap_score(
            required_proficiency="advanced", candidate_proficiency="beginner", importance=0.5
        )
        high_imp = gap_engine.compute_gap_score(
            required_proficiency="advanced", candidate_proficiency="beginner", importance=2.0
        )
        assert high_imp > low_imp

    def test_demand_raises_score(self):
        low_demand = gap_engine.compute_gap_score(
            required_proficiency="advanced", candidate_proficiency="beginner", demand=0.5
        )
        high_demand = gap_engine.compute_gap_score(
            required_proficiency="advanced", candidate_proficiency="beginner", demand=2.0
        )
        assert high_demand > low_demand


class TestSeverityClassification:
    def test_critical(self):
        assert gap_engine.classify_gap_severity(90.0) == "critical"

    def test_high(self):
        assert gap_engine.classify_gap_severity(60.0) == "high"

    def test_medium(self):
        assert gap_engine.classify_gap_severity(30.0) == "medium"

    def test_low(self):
        assert gap_engine.classify_gap_severity(10.0) == "low"


class TestComputeGaps:
    def test_deterministic_output(self):
        """Same inputs -> same gap list (order + values)."""
        gaps1 = gap_engine.compute_gaps(
            ["Docker", "Kubernetes", "Python"],
            resume_text="3 years of Python development.",
            jd_text="Expert in Docker, Kubernetes and Python.",
            jd_importance={"Docker": 2.0, "Kubernetes": 1.5, "Python": 1.0},
        )
        gaps2 = gap_engine.compute_gaps(
            ["Docker", "Kubernetes", "Python"],
            resume_text="3 years of Python development.",
            jd_text="Expert in Docker, Kubernetes and Python.",
            jd_importance={"Docker": 2.0, "Kubernetes": 1.5, "Python": 1.0},
        )
        assert gaps1 == gaps2

    def test_sorted_by_gap_score(self):
        gaps = gap_engine.compute_gaps(
            ["Kubernetes", "Docker"],
            resume_text="",
            jd_text="Expert in both.",
            jd_importance={"Kubernetes": 2.0, "Docker": 1.0},
        )
        scores = [g["gap_score"] for g in gaps]
        assert scores == sorted(scores, reverse=True)

    def test_severity_counts(self):
        gaps = [
            {"severity": "critical"},
            {"severity": "critical"},
            {"severity": "high"},
        ]
        counts = gap_engine.severity_counts(gaps)
        assert counts["critical"] == 2
        assert counts["high"] == 1
