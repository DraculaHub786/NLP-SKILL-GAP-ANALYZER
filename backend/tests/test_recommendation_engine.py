"""Tests for the Recommendation Engine.

Covers finding ranking (critical first), de-duplication of near-identical
findings, the Top-5 digest (no duplicated sections, info-noise filtered),
and the merge across three engines.
"""
from app.models.schemas import Finding
from app.services.recommendation_engine import (
    count_by_category,
    count_by_severity,
    dedupe_findings,
    merge_findings,
    rank_findings,
    top_fixes,
)


def _finding(
    severity: str,
    category: str = "ats",
    section: str | None = "experience",
    message: str = "Some finding",
) -> Finding:
    return Finding(
        category=category,
        severity=severity,
        section=section,
        message=message,
        why_it_matters="why",
        fix_suggestion="fix",
        example_before="before",
        example_after="after",
    )


class TestRankFindings:
    def test_critical_before_minor(self):
        critical = _finding("critical", message="Critical issue")
        minor = _finding("minor", message="Minor issue")
        ranked = rank_findings([minor, critical])
        assert ranked[0] is critical

    def test_stable_within_severity(self):
        first = _finding("minor", section="experience bullet 1", message="Bullet 1 issue")
        second = _finding("minor", section="experience bullet 2", message="Bullet 2 issue")
        ranked = rank_findings([first, second])
        assert ranked == [first, second]


class TestDedupeFindings:
    def test_same_pattern_collapses(self):
        f1 = _finding("minor", section="experience bullet 2", message="Bullet 2 starts with a weak phrase")
        f2 = _finding("minor", section="experience bullet 5", message="Bullet 5 starts with a weak phrase")
        deduped = dedupe_findings([f1, f2])
        assert len(deduped) == 1
        assert "2 similar" in deduped[0].message or "2 similar" in (deduped[0].section or "")

    def test_distinct_findings_kept(self):
        f1 = _finding("minor", message="Weak verb issue")
        f2 = _finding("major", message="Table structure detected")
        deduped = dedupe_findings([f1, f2])
        assert len(deduped) == 2

    def test_empty_input(self):
        assert dedupe_findings([]) == []


class TestTopFixes:
    def test_never_two_findings_same_section(self):
        findings = [
            _finding("critical", section="contact", message="Contact missing"),
            _finding("major", section="contact", message="Phone missing"),
            _finding("minor", section="experience bullet 1", message="Weak verb"),
            _finding("minor", section="experience bullet 2", message="No quantification"),
            _finding("minor", section="skills", message="Skills ungrouped"),
            _finding("info", section="dates", message="Gap detected"),
        ]
        fixes = top_fixes(findings, limit=5)
        sections = [f.section for f in fixes if f.section]
        assert len(sections) == len(set(sections)), f"Duplicate section in top fixes: {sections}"
        assert len(fixes) <= 5

    def test_info_filtered_when_enough_real_fixes(self):
        findings = [
            _finding("critical", section="a", message="Crit"),
            _finding("critical", section="b", message="Crit2"),
            _finding("critical", section="c", message="Crit3"),
            _finding("info", section="d", message="Info only"),
        ]
        fixes = top_fixes(findings, limit=5)
        assert all(f.severity != "info" for f in fixes)

    def test_empty_input(self):
        assert top_fixes([]) == []


class TestMergeFindings:
    def test_merges_all_engines(self):
        ats = [_finding("critical", category="ats", message="ATS issue")]
        content = [_finding("minor", category="content", message="Content issue")]
        match = [_finding("major", category="match", message="Match issue")]
        merged = merge_findings(ats, content, match)
        assert len(merged) == 3
        assert merged[0].severity == "critical"

    def test_merge_without_match_engine(self):
        ats = [_finding("minor", category="ats", message="ATS")]
        content = [_finding("minor", category="content", message="Content")]
        merged = merge_findings(ats, content)
        assert len(merged) == 2


class TestCounts:
    def test_count_by_severity(self):
        findings = [
            _finding("critical"),
            _finding("major"),
            _finding("minor"),
            _finding("minor"),
            _finding("info"),
        ]
        counts = count_by_severity(findings)
        assert counts == {"critical": 1, "major": 1, "minor": 2, "info": 1}

    def test_count_by_category(self):
        findings = [
            _finding("minor", category="ats"),
            _finding("minor", category="content"),
            _finding("minor", category="match"),
        ]
        counts = count_by_category(findings)
        assert counts == {"ats": 1, "content": 1, "match": 1}
