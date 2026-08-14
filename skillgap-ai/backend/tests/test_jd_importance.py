"""Tests for JD importance weighting: mention frequency + section context."""
from app.services.jd_importance import compute_importance


def test_skills_not_mentioned_get_floor_weight():
    importance = compute_importance("We use Python a lot.", ["Rust"])
    assert importance["Rust"] == 0.5


def test_more_mentions_higher_weight():
    jd = "Python everywhere. Python in services. Python in scripts. Docker once."
    importance = compute_importance(jd, ["Python", "Docker"])
    assert importance["Python"] > importance["Docker"]


def test_must_have_section_boosts_weight():
    jd = (
        "Looking for a backend engineer.\n"
        "Requirements:\n"
        "- Python\n"
        "Nice to have:\n"
        "- Rust\n"
    )
    importance = compute_importance(jd, ["Python", "Rust"])
    # Python sits in the must-have zone and gets the 1.5x boost on its mention.
    assert importance["Python"] > importance["Rust"]


def test_empty_skills_returns_empty_dict():
    assert compute_importance("Any text", []) == {}


def test_no_mentions_all_floor():
    importance = compute_importance("Nothing here mentions skills.", ["Python", "SQL"])
    assert importance == {"Python": 0.5, "SQL": 0.5}


def test_weights_are_within_intervals():
    jd = "Python\nPython\nPython\nGo\nKubernetes\nRequirements:\nSQL"
    importance = compute_importance(jd, ["Python", "Go", "Kubernetes", "SQL"])
    for skill, weight in importance.items():
        assert 0.5 <= weight <= 2.0
