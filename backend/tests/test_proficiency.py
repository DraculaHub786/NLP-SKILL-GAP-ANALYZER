"""Phase 1.5 tests: Proficiency Estimation.

Verifies:
- Verb cues map to the correct level
- No evidence -> Beginner/Unverified
- Conflicting cues resolve to the stronger signal
- Duración mentions scale level correctly
"""
import pytest

from app.nlp import proficiency


class TestProficiencyLevels:
    def test_no_evidence_beginner(self):
        result = proficiency.estimate_proficiency("", "Python")
        assert result["level"] == "beginner"
        assert result["verified"] is False
        assert result["score"] == 1

    def test_weak_cue_beginner(self):
        text = "Familiar with Python and some experience with SQL."
        result = proficiency.estimate_proficiency(text, "Python")
        assert result["level"] == "beginner"
        assert result["verified"] is True

    def test_single_ownership_verb_intermediate(self):
        text = "Implemented microservices in Python for a fintech product."
        result = proficiency.estimate_proficiency(text, "Python")
        assert result["level"] == "intermediate"

    def test_multiple_ownership_verbs_advanced(self):
        text = "Led a team and architected distributed systems in Go."
        result = proficiency.estimate_proficiency(text, "Go")
        assert result["level"] == "advanced"

    def test_expert_cue_wins(self):
        text = "Expert in Python with deep experience building ML systems."
        result = proficiency.estimate_proficiency(text, "Python")
        assert result["level"] == "expert"

    def test_duration_3_years_intermediate(self):
        text = "3 years of Python development."
        result = proficiency.estimate_proficiency(text, "Python")
        assert result["level"] == "intermediate"

    def test_duration_6_years_advanced(self):
        text = "6 years of hands-on Python experience."
        result = proficiency.estimate_proficiency(text, "Python")
        assert result["level"] == "advanced"


class TestProficiencyResolution:
    def test_conflicting_cues_resolve_stronger(self):
        """Expert cue + weak cue -> expert (stronger wins)."""
        text = "Expert in Python but only limited experience with Django."
        result = proficiency.estimate_proficiency(text, "Python")
        assert result["level"] == "expert"

    def test_evidence_is_collected(self):
        text = "5 years of Python. Led a team."
        result = proficiency.estimate_proficiency(text, "Python")
        assert len(result["evidence"]) >= 1


class TestEstimateAll:
    def test_batch(self):
        text = "Expert in Python and 3 years of JavaScript."
        results = proficiency.estimate_all(text, ["Python", "JavaScript"])
        assert len(results) == 2
        assert results[0]["skill"] == "Python"
        assert results[1]["skill"] == "JavaScript"
