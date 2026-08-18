"""Recommendation Engine — turns findings into an actionable, prioritized fix list.

Merges findings from all three engines (ATS / Content / Match), ranks them by
severity × estimated score impact, de-duplicates near-identical findings, and
produces the "Top 5 Fixes" digest.

Error contract: pure functions — never raise; empty input yields empty output.
"""
from __future__ import annotations

import re
from collections import Counter

from app.models.schemas import Finding

# Severity ranking: higher = more urgent.
SEVERITY_RANK = {"critical": 4, "major": 3, "minor": 2, "info": 1}

# Rough per-severity score-impact estimate used to sort equally-severe findings.
SEVERITY_IMPACT = {"critical": 15.0, "major": 8.0, "minor": 3.0, "info": 1.0}


def _rank_key(finding: Finding) -> tuple[int, float]:
    """Sort key: (severity rank, estimated score impact)."""
    return (
        SEVERITY_RANK.get(finding.severity, 0),
        SEVERITY_IMPACT.get(finding.severity, 0.0),
    )


def rank_findings(findings: list[Finding]) -> list[Finding]:
    """Sorts findings by severity (critical first), then score impact, while
    preserving the original (document) order within the same severity."""
    indexed = list(enumerate(findings))
    indexed.sort(key=lambda t: (-_rank_key(t[1])[0], -_rank_key(t[1])[1], t[0]))
    return [f for _, f in indexed]


def _dedup_key(finding: Finding) -> str:
    """Groups findings that are near-identical: same category + same message
    pattern (stripped of the per-bullet index)."""
    category = finding.category or ""
    message = (finding.message or "").strip()
    message_norm = re.sub(r"bullet \d+", "bullet N", message, flags=re.IGNORECASE)
    return f"{category}|{message_norm.lower()}"


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Collapses near-identical findings into one representative per group.

    The representative keeps the most severe/earliest instance and records the
    line/section references of the collapsed ones in `section`.
    """
    if not findings:
        return []

    # Preserve original order for deterministic output.
    groups: dict[str, list[Finding]] = {}
    order: list[str] = []
    for finding in findings:
        key = _dedup_key(finding)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(finding)

    out: list[Finding] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            out.append(group[0])
            continue
        # Representative = most severe first (then earliest).
        representative = min(group, key=lambda f: (-SEVERITY_RANK.get(f.severity, 0),))
        references = sorted({f.section for f in group if f.section}, key=lambda s: (s or ""))
        if len(references) > 1:
            representative.section = ", ".join(references)
        representative.message = (
            representative.message + f" (applies to {len(group)} similar bullets/items)"
        )
        out.append(representative)
    return out


def merge_findings(
    ats_findings: list[Finding],
    content_findings: list[Finding],
    match_findings: list[Finding] | None = None,
) -> list[Finding]:
    """Merges findings from all engines, de-duplicates, and ranks them."""
    all_findings = list(ats_findings) + list(content_findings) + list(match_findings or [])
    deduped = dedupe_findings(all_findings)
    return rank_findings(deduped)


def top_fixes(findings: list[Finding], limit: int = 5) -> list[Finding]:
    """The 'Top 5 Fixes' digest — the single most useful findings for quick
    action. Never includes two findings about the exact same bullet/section."""
    ranked = rank_findings(findings)
    selected: list[Finding] = []
    seen_sections: set[str] = set()

    for finding in ranked:
        if finding.severity == "info" and len(selected) >= 3:
            # Digests should be action-oriented; info findings are noise once
            # enough real fixes are captured.
            continue
        # Skip a finding whose primary section is already covered, unless the
        # new one is more severe.
        section = finding.section or ""
        if section and section in seen_sections:
            continue
        selected.append(finding)
        if section:
            seen_sections.add(section)
        if len(selected) >= limit:
            break

    return selected


def count_by_severity(findings: list[Finding]) -> dict[str, int]:
    """Aggregates findings by severity for the UI's summary strip."""
    counts = Counter(f.severity for f in findings)
    return {
        "critical": counts.get("critical", 0),
        "major": counts.get("major", 0),
        "minor": counts.get("minor", 0),
        "info": counts.get("info", 0),
    }


def count_by_category(findings: list[Finding]) -> dict[str, int]:
    """Aggregates findings by engine category (ats/content/match)."""
    counts = Counter(f.category or "unknown" for f in findings)
    return {
        "ats": counts.get("ats", 0),
        "content": counts.get("content", 0),
        "match": counts.get("match", 0),
    }
