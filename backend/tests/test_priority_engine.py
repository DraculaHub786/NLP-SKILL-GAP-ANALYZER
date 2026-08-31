"""Phase 2 tests: Priority Engine.

Verifies:
- Priority ordering follows gap severity + demand
- Demand changes reorder the priority list
- top_priority_skills returns expected subset
"""
import pytest

from app.analysis import priority_engine


class TestComputePriority:
    def test_higher_gap_higher_priority(self):
        low = priority_engine.compute_priority("Docker", gap_score=20.0, demand=1.0)
        high = priority_engine.compute_priority("Kubernetes", gap_score=80.0, demand=1.0)
        assert high["priority_score"] > low["priority_score"]

    def test_demand_raises_priority(self):
        low_demand = priority_engine.compute_priority("Kubernetes", gap_score=50.0, demand=0.5)
        high_demand = priority_engine.compute_priority("Kubernetes", gap_score=50.0, demand=2.0)
        assert high_demand["priority_score"] > low_demand["priority_score"]

    def test_severity_mapping(self):
        entry = priority_engine.compute_priority("Python", gap_score=90.0, demand=1.0)
        assert entry["severity"] == "critical"
        assert entry["skill"] == "Python"

    def test_priority_bounds(self):
        entry = priority_engine.compute_priority("Python", gap_score=100.0, demand=3.0)
        assert 0.0 <= entry["priority_score"] <= 100.0


class TestBuildPriorityList:
    def test_sorted_by_priority(self):
        gaps = [
            {"skill": "Docker", "gap_score": 30.0, "importance": 1.0},
            {"skill": "Kubernetes", "gap_score": 80.0, "importance": 1.0},
            {"skill": "Python", "gap_score": 90.0, "importance": 1.0},
        ]
        prioritized = priority_engine.build_priority_list(gaps)
        scores = [p["priority_score"] for p in prioritized]
        assert scores == sorted(scores, reverse=True)

    def test_demand_changes_order(self):
        """When demand is applied, a lower-gap but high-demand skill can
        outrank a higher-gap, low-demand skill."""
        gaps = [
            {"skill": "LowDemandHighGap", "gap_score": 80.0, "importance": 1.0},
            {"skill": "HighDemandLowGap", "gap_score": 40.0, "importance": 1.0},
        ]
        demand_map = {"LowDemandHighGap": 0.5, "HighDemandLowGap": 2.0}
        prioritized = priority_engine.build_priority_list(gaps, demand_map=demand_map)
        # The high-demand skill should now be first.
        assert prioritized[0]["skill"] == "HighDemandLowGap"

    def test_top_priority_skills(self):
        gaps = [
            {"skill": "A", "gap_score": 90.0, "importance": 1.0},
            {"skill": "B", "gap_score": 80.0, "importance": 1.0},
            {"skill": "C", "gap_score": 70.0, "importance": 1.0},
            {"skill": "D", "gap_score": 30.0, "importance": 1.0},
        ]
        prioritized = priority_engine.build_priority_list(gaps, demand_map={"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0})
        top3 = priority_engine.top_priority_skills(prioritized, top_n=3)
        assert len(top3) == 3
