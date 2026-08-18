"""Tests for the Content Quality Analyzer engine.

Covers weak-verb detection with in-family suggestions, quantification
classification, passive voice, tense mismatch, headline metrics, and the
empty-input edge case.
"""
import pytest

from app.services.content_quality_analyzer import analyze_content


class TestWeakVerbs:
    def test_responsible_for_flagged_with_suggestion(self):
        """'Responsible for' bullet → minor finding with a strong-verb suggestion."""
        _, findings = analyze_content(["Responsible for deploying services to AWS."])
        weak = [f for f in findings if "weak phrase" in f.message.lower()]
        assert len(weak) == 1
        assert weak[0].severity == "minor"
        assert weak[0].example_after  # suggestion present

    def test_worked_on_flagged(self):
        _, findings = analyze_content(["Worked on the payment gateway."])
        weak = [f for f in findings if "weak phrase" in f.message.lower()]
        assert len(weak) == 1

    def test_strong_verb_not_flagged(self):
        _, findings = analyze_content(["Led a team of 4 to ship the platform."])
        weak = [f for f in findings if "weak phrase" in f.message.lower()]
        assert len(weak) == 0

    def test_weak_verb_count(self):
        score, _ = analyze_content([
            "Responsible for QA.",
            "Helped with onboarding.",
            "Reduced build time by 40%.",
        ])
        assert score.weak_verb_count == 2


class TestQuantification:
    def test_quantified_bullet_pct(self):
        score, _ = analyze_content([
            "Reduced latency by 40%.",
            "Built the dashboard.",
            "Served 10K users daily.",
        ])
        assert score.quantified_bullet_pct == pytest.approx(66.7, abs=0.1)

    def test_unquantified_bullet_flagged(self):
        _, findings = analyze_content(["Built the reporting module."])
        quant = [f for f in findings if "no quantified outcome" in f.message.lower()]
        assert len(quant) == 1

    def test_zero_bullets_no_crash(self):
        score, findings = analyze_content([])
        assert score.quantified_bullet_pct == 0.0
        assert findings == []


class TestPassiveVoice:
    def test_passive_detected(self):
        _, findings = analyze_content(["The system was built using Django."])
        passive = [f for f in findings if "passive voice" in f.message.lower()]
        assert len(passive) >= 1

    def test_active_not_flagged_as_passive(self):
        _, findings = analyze_content(["Built the system using Django."])
        passive = [f for f in findings if "passive voice" in f.message.lower()]
        assert len(passive) == 0


class TestAchievementRatio:
    def test_all_quantified_ratio_high(self):
        score, _ = analyze_content([
            "Generated $1M revenue.",
            "Cut costs by 20%.",
            "Launched 3 products.",
        ])
        assert score.achievement_duty_ratio >= 0.9

    def test_duty_bullets_lower_ratio(self):
        score, _ = analyze_content([
            "Attended meetings.",
            "Filled in timesheets.",
            "Reduced turnaround by 2 days.",
        ])
        assert score.achievement_duty_ratio < 0.5

    def test_empty_ratio_zero(self):
        score, _ = analyze_content([])
        assert score.achievement_duty_ratio == 0.0


class TestTense:
    def test_past_tense_in_current_role_info(self):
        """A past-tense verb in the (default last) current role → info finding."""
        _, findings = analyze_content(["Led the team."])
        tense = [f for f in findings if "tense" in f.message.lower()]
        assert len(tense) >= 1
        assert tense[0].severity == "info"


class TestScoreBounds:
    def test_score_in_range(self):
        score, _ = analyze_content([
            "Responsible for stuff.",
            "Did things.",
            "Worked on tasks.",
            "Assisted with work.",
        ])
        assert 0.0 <= score.score <= 100.0

    def test_strong_resume_scores_high(self):
        score, _ = analyze_content([
            "Led a team of 6 to launch a platform serving 50K users.",
            "Reduced infrastructure costs by 40%.",
            "Architected a microservices migration with zero downtime.",
            "Mentored 3 junior engineers to promotion.",
        ])
        assert score.score > 70, f"Strong resume should score high, got {score.score}"
