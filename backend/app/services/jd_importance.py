"""Computes per-skill importance weights from the raw JD text.

Strategy (master plan §3.5):
- Base weight = normalized mention count of the skill in the JD text.
  Mentions are matched on word boundaries so 'Go' in 'MongoDB' or 'C' in
  'React' don't create false counts.
- Skills mentioned inside a 'Requirements'/'Must-have'/'Qualifications'
  section get a boost over those in 'Nice-to-have' sections.

Returns a dict mapping each jd_skill canonical name to a float weight in
[0.5, 2.0], so compute_gap_report can scale matched/missing contributions.
"""
import re

_MUST_HAVE_HEADERS = re.compile(
    r"(requirements|must have|must-have|qualifications|what you.{0,10}need|"
    r"candidate profile|your profile|we need|required skills|essential skills|"
    r"key skills|skills and experience)",
    re.IGNORECASE,
)
_NICE_HAVE_HEADERS = re.compile(
    r"(nice to have|nice-to-have|bonus points|preferred qualifications|"
    r"bonus skills|would be a plus|a plus|good to have)",
    re.IGNORECASE,
)

# Fix #8: Nice-to-have sections get a genuinely lower weight than the 1.0
# baseline, so must-have vs nice-to-have skills are actually differentiated.
_NICE_TO_HAVE_WEIGHT = 0.7


def _mention_pattern(skill: str) -> re.Pattern:
    """Word-boundary pattern for a skill so 'Go' doesn't match 'MongoDB'."""
    escaped = re.escape(skill)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def compute_importance(jd_text: str, jd_skills: list[str]) -> dict[str, float]:
    """Returns {skill: weight} for every jd_skill based on mention frequency
    and section context. Skills with zero mentions get a floor weight of 0.5
    so they participate in scoring without dominating."""
    if not jd_skills:
        return {}

    text = jd_text or ""
    lines = text.splitlines()
    patterns = {skill: _mention_pattern(skill) for skill in jd_skills}

    # Section context: a must-have header boosts all lines after it until a
    # nice-to-have header resets the zone (and vice versa).
    boost = 1.0
    boosts_by_line: list[float] = []
    for line in lines:
        if _MUST_HAVE_HEADERS.search(line):
            boost = 1.5
        elif _NICE_HAVE_HEADERS.search(line):
            boost = _NICE_TO_HAVE_WEIGHT
        boosts_by_line.append(boost)

    weighted_mentions: dict[str, float] = {s: 0.0 for s in jd_skills}

    for line, line_boost in zip(lines, boosts_by_line):
        for skill in jd_skills:
            matches = patterns[skill].findall(line)
            if matches:
                weighted_mentions[skill] += len(matches) * line_boost

    max_mentions = max(weighted_mentions.values()) or 1.0
    normalized: dict[str, float] = {}
    for skill in jd_skills:
        raw = weighted_mentions[skill]
        if raw <= 0:
            normalized[skill] = 0.5
        else:
            # Scale to [0.5, 2.0]: 1.0 ≈ average mention rate in the JD.
            normalized[skill] = round(0.5 + 1.5 * (raw / max_mentions), 2)
    return normalized
