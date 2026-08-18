"""Tests for the Unified Scoring Engine.

Covers the 3-sub-score rollup, weight configurability, the explicit no-JD
branch (match omitted → 50/50 ATS + Content), and score explainability
breakdowns.
"""
import pytest

from app.models.schemas import AtScore, ContentScore, Finding, GapReport, MatchScore, ResumeIntelligenceReport
from app.services.scoring_engine import (
    apply_report_scores,
    score_ats,
    score_content,
    score_match,
    score_overall,
)


def _finding(severity: str, category: str = "ats", section: str | None = "test") -> Finding:
    return Finding(
        category=category,
        severity=severity,
        section=section,
        message="Test finding",
        why_it_matters="why",
        fix_suggestion="fix",
        example_before="before",
        example_after="after",
    )


class TestScoreAts:
    def test_clean_resume_scores_100(self):
        score, breakdown = score_ats([])
        assert score == 100.0
        assert breakdown["penalty"] == 0.0

    def test_critical_flags_deduct(self):
        score, breakdown = score_ats([_finding("critical")])
        assert score == pytest.approx(85.0)
        assert breakdown["critical_count"] == 1

    def test_many_flags_floor_at_zero(self):
        score, _ = score_ats([_finding("critical")] * 7)
        assert score == 0.0

    def test_severity_ordering(self):
        """More critical flags → strictly lower score than fewer critical flags."""
        s_many, _ = score_ats([_finding("critical"), _finding("major")])
        s_few, _ = score_ats([_finding("minor")])
        assert s_many < s_few


class TestScoreContent:
    def test_score_passthrough_and_breakdown(self):
        content = ContentScore(score=72.5, quantified_bullet_pct=55.0, weak_verb_count=2, achievement_duty_ratio=0.6)
        score, breakdown = score_content(content)
        assert score == 72.5
        assert breakdown["quantified_bullet_pct"] == 55.0
        assert breakdown["weak_verb_count"] == 2
        assert breakdown["achievement_duty_ratio"] == 0.6


class TestScoreMatch:
    def test_match_score_from_gap_report(self):
        gap = GapReport(match_score=85.0, matched=[], missing=["Docker"], bonus=["SQL"])
        score, breakdown = score_match(gap)
        assert score == 85.0
        assert breakdown["matched_count"] == 0
        assert breakdown["missing_count"] == 1
        assert breakdown["bonus_count"] == 1


class TestScoreOverall:
    def test_full_weights(self):
        overall, breakdown = score_overall(100.0, 80.0, 60.0)
        # 0.3*100 + 0.3*80 + 0.4*60 = 30 + 24 + 24 = 78
        assert overall == pytest.approx(78.0)
        assert breakdown["match_contribution"] == pytest.approx(24.0)

    def test_no_jd_reweights_to_5050(self):
        overall, breakdown = score_overall(100.0, 50.0, None)
        # 0.5*100 + 0.5*50 = 75
        assert overall == pytest.approx(75.0)
        assert breakdown["match_contribution"] is None
        assert breakdown["ats_weight"] == pytest.approx(0.5)
        assert breakdown["content_weight"] == pytest.approx(0.5)

    def test_custom_weights_respected(self):
        overall, _ = score_overall(100.0, 100.0, 0.0, weights={"ats": 0.1, "content": 0.1, "match": 0.8})
        # 0.1*100 + 0.1*100 + 0.8*0 = 20
        assert overall == pytest.approx(20.0)

    def test_zero_total_weights(self):
        overall, breakdown = score_overall(50.0, 50.0, None, weights={"ats": 0, "content": 0, "match": 0})
        assert overall == 0.0
        assert "error" in breakdown


class TestApplyReportScores:
    def _report(self, match: MatchScore | None) -> ResumeIntelligenceReport:
        return ResumeIntelligenceReport(
            ats_score=AtScore(score=100.0, format="pdf"),
            content_score=ContentScore(score=80.0, quantified_bullet_pct=50.0, weak_verb_count=0, achievement_duty_ratio=0.5),
            match_score=match,
            overall_score=0.0,
        )

    def test_with_jd_populates_overall(self):
        report = self._report(MatchScore(score=60.0, matched_count=1, missing_count=1))
        apply_report_scores(report)
        assert report.overall_score == pytest.approx(78.0)
        assert report.metadata["score_breakdown"]["match_contribution"] is not None
        assert "no_jd_mode" not in report.metadata

    def test_no_jd_sets_no_jd_mode(self):
        report = self._report(None)
        apply_report_scores(report)
        # 0.5*100 + 0.5*80 = 90
        assert report.overall_score == pytest.approx(90.0)
        assert report.metadata["no_jd_mode"] is True

    def test_gap_data_embedded(self):
        gap = GapReport(match_score=60.0, matched=[], missing=["Kubernetes"], bonus=["Redis"], recommendations=[])
        report = self._report(None)
        apply_report_scores(report, gap=gap)
        assert report.missing == ["Kubernetes"]
        assert report.bonus == ["Redis"]
        assert report.match_score is not None
        assert report.match_score.missing_count == 1
