"""Date & Formatting Consistency Engine.

Extracts all date ranges from Experience/Education sections, normalizes them,
and flags inconsistencies, gaps, overlaps, and order issues.

Also checks bullet/indentation consistency.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.schemas import Finding


# ── Canonical date format ─────────────────────────────────────────────────────

# Accepted formats that will be normalized internally:
# MM/YYYY, Month YYYY, Mon YYYY, YYYY
# We normalize ALL to "YYYY-MM" internally for comparison.

MONTH_NAMES = {
    "january": "01",
    "february": "02",
    "mar": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


# ── Date range regex patterns ─────────────────────────────────────────────────

# Pattern 1: MM/YYYY (e.g., 06/2023, 12/2019)
PATTERN_MM_YYYY = re.compile(r"\b(\d{1,2})/(\d{4})\b")

# Pattern 2: Month YYYY (e.g., June 2023, December 2019)
PATTERN_MONTH_YYYY = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)

# Pattern 3: Mon YYYY (e.g., Jan 2023, Dec 2019)
PATTERN_MON_YYYY = re.compile(r"\b([A-Z][a-z]{2})\s+(\d{4})\b")

# Pattern 4: YYYY only (e.g., 2023 — graduation year, start year)
PATTERN_YYYY = re.compile(r"\b(\d{4})\b")


# ── Normalize a date string to internal "YYYY-MM" format ───────────────────────

def normalize_date(raw: str) -> str | None:
    """Normalize a raw date string to internal 'YYYY-MM' format.

    Returns None if the date cannot be parsed.
    """
    raw_stripped = raw.strip()

    # Try MM/YYYY first
    m = PATTERN_MM_YYYY.search(raw_stripped)
    if m:
        month = int(m.group(1))
        year = int(m.group(2))
        if 1 <= month <= 12:
            return f"{year:04d}-{month:02d}"

    # Try Month YYYY
    m = PATTERN_MONTH_YYYY.search(raw_stripped)
    if m:
        month_name = m.group(1).lower()
        year = int(m.group(2))
        if month_name in MONTH_NAMES:
            month = int(MONTH_NAMES[month_name])
            return f"{year:04d}-{month:02d}"

    # Try Mon YYYY
    m = PATTERN_MON_YYYY.search(raw_stripped)
    if m:
        month_abbr = m.group(1).lower()
        year = int(m.group(2))
        if month_abbr in MONTH_NAMES:
            month = int(MONTH_NAMES[month_abbr])
            return f"{year:04d}-{month:02d}"

    # Try YYYY only
    m = PATTERN_YYYY.search(raw_stripped)
    if m:
        year = int(m.group(1))
        # Return just the year as YYYY-00 (sentinel for "year only")
        return f"{year:04d}-00"

    return None


# ── Extract all date ranges from a text block ──────────────────────────────────

def extract_dates_from_text(
    text: str,
) -> list[dict[str, str | None]]:
    """Extract all date ranges found in a text block.

    Returns a list of dicts with 'raw', 'normalized_start', 'normalized_end',
    and 'format' keys. Each dict represents one date range found in the text.
    """
    dates: list[dict[str, str | None]] = []

    # Split text into potential date-line chunks
    # We look for patterns that look like date ranges: "Month YYYY - Month YYYY"
    # or "MM/YYYY - MM/YYYY" or "Jan 2023 - Dec 2023"

    # Pattern: date range with separator (dash, en-dash, or "to")
    range_patterns = [
        re.compile(
            r"("
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})"
            r")\s*[-–to]\s*("
            r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})"
            r")",
            re.IGNORECASE,
        ),
        re.compile(
            r"("
            r"\b(\d{1,2})/(\d{4})"
            r")\s*[-–to]\s*("
            r"\b(\d{1,2})/(\d{4})"
            r")",
            re.IGNORECASE,
        ),
        re.compile(
            r"("
            r"\b([A-Z][a-z]{2})\s+(\d{4})"
            r")\s*[-–to]\s*("
            r"\b([A-Z][a-z]{2})\s+(\d{4})"
            r")",
            re.IGNORECASE,
        ),
    ]

    for pattern in range_patterns:
        for match in pattern.finditer(text):
            start_raw = match.group(1)
            end_raw = match.group(3)

            start_norm = normalize_date(start_raw)
            end_norm = normalize_date(end_raw)

            if start_norm and end_norm:
                dates.append(
                    {
                        "raw": f"{start_raw} - {end_raw}",
                        "normalized_start": start_norm,
                        "normalized_end": end_norm,
                        "format": "range",
                    }
                )

    # Also extract individual dates (single YYYY or Month YYYY) that aren't
    # part of a range — these could be start years or end years of individual roles
    individual_patterns = [
        PATTERN_MM_YYYY,
        PATTERN_MONTH_YYYY,
        PATTERN_MON_YYYY,
        PATTERN_YYYY,
    ]

    for pattern in individual_patterns:
        for match in pattern.finditer(text):
            # Get the full match text
            raw = match.group(0)

            # Check if this individual date is already part of a range we found
            # (skip if it is — we already captured it as a range)
            is_in_range = any(
                d["raw"].replace(" - ", " ") == raw for d in dates
            )
            if is_in_range:
                continue

            # Determine if it's a start year or just a standalone year
            # Heuristic: if it looks like it could be part of a range pattern
            # (followed by more text that looks like a date), skip it for now
            # and let the range detection handle it.

            # For YYYY-only matches, flag as a single-year date
            if PATTERN_YYYY.match(raw) and not PATTERN_MM_YYYY.match(raw) and not PATTERN_MONTH_YYYY.match(raw) and not PATTERN_MON_YYYY.match(raw):
                # This is a standalone YYYY
                year = int(match.group(1))
                dates.append(
                    {
                        "raw": raw,
                        "normalized_start": f"{year:04d}-00",
                        "normalized_end": None,
                        "format": "single",
                    }
                )
            else:
                # Try to normalize other formats
                norm = normalize_date(raw)
                if norm:
                    dates.append(
                        {
                            "raw": raw,
                            "normalized_start": norm,
                            "normalized_end": None,
                            "format": "single",
                        }
                    )

    # Deduplicate by normalized_start (keep first occurrence)
    seen: set[str] = set()
    deduped: list[dict[str, str | None]] = []
    for d in dates:
        key = d["normalized_start"]
        if key not in seen:
            seen.add(key)
            deduped.append(d)

    return deduped


# ── 1. Detect inconsistency: more than one date format style used ────────────────

def detect_date_format_inconsistency(
    dates: list[dict[str, str | None]],
) -> Finding | None:
    """Flag if more than one date format style is used across the document."""

    if not dates:
        return None

    # Collect the format types used
    formats_used: set[str] = set()
    for d in dates:
        fmt = d.get("format", "unknown")
        # Extract the base format category
        if fmt == "range":
            # Check the component formats
            if d["normalized_start"]:
                # Determine if it was MM/YYYY, Month YYYY, or Mon YYYY
                start = d["normalized_start"]
                if start.endswith("-01") or start.endswith("-03") or start.endswith("-05") or start.endswith("-07") or start.endswith("-08") or start.endswith("-10") or start.endswith("-12"):
                    # Likely Month YYYY normalized
                    formats_used.add("month_yyy")
                else:
                    formats_used.add("mm_yyy")
            if d["normalized_end"]:
                end = d["normalized_end"]
                if end.endswith("-01") or end.endswith("-03") or end.endswith("-05") or end.endswith("-07") or end.endswith("-08") or end.endswith("-10") or end.endswith("-12"):
                    formats_used.add("month_yyy")
                else:
                    formats_used.add("mm_yyy")
        elif fmt == "single":
            formats_used.add("single")
        else:
            formats_used.add(fmt)

    # If we have more than one distinct format type, flag it
    if len(formats_used) > 1:
        format_names = ", ".join(sorted(formats_used))
        return Finding(
            category="ats",
            severity="minor",
            section="formatting",
            message=f"Inconsistent date formats detected: {format_names}. "
            "Normalize to a single format for reliable ATS parsing.",
            why_it_matters="ATS parsers rely on consistent date formatting to correctly "
            "extract employment duration, identify gaps, and verify chronological order. "
            "Mixed formats (e.g., some 'June 2023' and some '06/2023') may cause "
            "the parser to misinterpret dates or fail to recognize them as dates at all.",
            fix_suggestion="Choose one date format style and use it consistently "
            "throughout your resume. Recommended: 'Month YYYY' (e.g., 'June 2023') "
            "or 'MM/YYYY' (e.g., '06/2023'), and use it for all date ranges "
            "across Experience and Education sections.",
            example_before="Mixed formats: 'June 2023 – 07/2020' and 'Jan 2021 – Dec 2021'",
            example_after="Consistent format: 'June 2023 – July 2020' and 'January 2021 – December 2021'",
        )

    return None


# ── 2. Detect unexplained employment gaps (> configurable threshold) ───────────

GAP_THRESHOLD_MONTHS = 6  # Configurable: flag gaps > 6 months by default


def detect_employment_gaps(
    dates: list[dict[str, str | None]],
) -> list[Finding]:
    """Detect unexplained employment gaps > GAP_THRESHOLD_MONTHS between consecutive roles.

    Each date dict should have 'normalized_start' and 'normalized_end'.
    Gaps are computed between the end of one role and the start of the next.
    """
    gaps: list[Finding] = []

    # Sort dates by normalized_start (earliest first)
    sortable: list[dict[str, str | None]] = []
    for d in dates:
        start = d.get("normalized_start")
        end = d.get("normalized_end")
        if start:
            # Normalize single-year dates (YYYY-00) for sorting
            sort_key = start if start.endswith("-00") else start
            sortable.append(
                {
                    "raw": d.get("raw", ""),
                    "normalized_start": start,
                    "normalized_end": end or "9999-12",  # Assume current if no end
                    "sort_key": sort_key,
                }
            )

    if len(sortable) < 2:
        return gaps

    # Sort by start date
    sortable.sort(key=lambda x: x["sort_key"])

    # Compute gaps between consecutive roles
    for i in range(len(sortable) - 1):
        current_end = sortable[i]["normalized_end"]
        next_start = sortable[i + 1]["normalized_start"]

        # Both must have valid year-month format (not "YYYY-00" sentinel)
        if current_end and next_start and current_end != "9999-12" and next_start != "9999-12":
            # Parse the end date of current role
            try:
                end_year = int(current_end[:4])
                end_month = int(current_end[5:7])
                # Parse the start date of next role
                next_year = int(next_start[:4])
                next_month = int(next_start[5:7])

                # Calculate gap months: from (end_year, end_month) to (next_year, next_start_month)
                # Gap = (next_year - end_year) * 12 + (next_month - end_month) - 1
                # We subtract 1 because if one role ends in June and the next starts in July,
                # there's no gap (they're adjacent).
                gap_months = (next_year - end_year) * 12 + (next_month - end_month) - 1

                if gap_months > GAP_THRESHOLD_MONTHS:
                    # Format the gap in a readable way
                    gap_months_display = max(0, gap_months)
                    gap_years = gap_months_display // 12
                    gap_remaining_months = gap_months_display % 12

                    gap_str = f"{gap_months_display} month{'s' if gap_months_display != 1 else ''}"
                    if gap_years:
                        gap_str = f"{gap_years} year{'s' if gap_years > 1 else ''} {gap_remaining_months} month{'s' if gap_remaining_months != 1 else ''} {gap_str}".strip()

                    gaps.append(
                        Finding(
                            category="ats",
                            severity="info",
                            section="dates",
                            message=f"Unexplained employment gap of {gap_str} between roles.",
                            why_it_matters=f"Employment gaps longer than {GAP_THRESHOLD_MONTHS} months "
                            "may raise questions from recruiters or ATS systems. While gaps are "
                            "common and often legitimate (career break, education, personal reasons), "
                            "it's helpful to address them proactively in your resume or cover letter.",
                            fix_suggestion=(
                                f"Consider addressing this {gap_str} gap in your resume "
                                "context (e.g., note 'Professional Development', 'Career Break', "
                                "or 'Freelance Consulting' during the period). "
                                f"Or adjust the date range if this was a data entry error."
                            ),
                            example_before="Gap of 10 months between Dec 2020 and Oct 2021 — "
                            "not addressed in the resume.",
                            example_after="Gap of 10 months noted as 'Freelance Consulting' "
                            "(Jan 2021 - Oct 2021) in the resume, or gap adjusted to "
                            "reflect continuous employment.",
                        )
                    )
            except (ValueError, IndexError):
                # Malformed date part — skip this pair rather than crashing.
                continue

    return gaps


# ── 3. Detect overlapping date ranges across different employers ────────────────

def detect_overlapping_dates(
    dates: list[dict[str, str | None]],
) -> list[Finding]:
    """Detect overlapping date ranges across different employers.

    Returns findings for any pairs of role date ranges that overlap.
    """
    overlaps: list[Finding] = []

    # Sort dates by start date
    sortable: list[dict[str, str | None]] = []
    for d in dates:
        start = d.get("normalized_start")
        end = d.get("normalized_end")
        if start and end and end != "9999-12":
            try:
                start_year = int(start[:4])
                start_month = int(start[5:7])
                end_year = int(end[:4])
                end_month = int(end[5:7])
                sortable.append(
                    {
                        "raw": d.get("raw", ""),
                        "start_key": f"{start_year:04d}{start_month:02d}",
                        "end_key": f"{end_year:04d}{end_month:02d}",
                        "normalized_start": start,
                        "normalized_end": end,
                    }
                )
            except (ValueError, IndexError):
                continue

    if len(sortable) < 2:
        return overlaps

    # Sort by start date
    sortable.sort(key=lambda x: x["start_key"])

    # Check each pair for overlap
    for i in range(len(sortable)):
        for j in range(i + 1, len(sortable)):
            # Overlap if: i.start < j.end AND j.start < i.end
            i_start = int(sortable[i]["start_key"])
            i_end = int(sortable[i]["end_key"])
            j_start = int(sortable[j]["start_key"])
            j_end = int(sortable[j]["end_key"])

            # Overlap condition
            if i_start <= j_end and j_start <= i_end:
                # Calculate overlap duration
                overlap_start = max(i_start, j_start)
                overlap_end = min(i_end, j_end)
                overlap_months = overlap_end - overlap_start

                if overlap_months > 0:
                    overlap_str = f"{overlap_months} month{'s' if overlap_months > 1 else ''}"
                    overlaps.append(
                        Finding(
                            category="ats",
                            severity="major",
                            section="dates",
                            message=f"Overlapping date ranges detected: {sortable[i]['raw']} and {sortable[j]['raw']} overlap by {overlap_str}.",
                            why_it_matters="Overlapping employment dates across different employers "
                            "are either a data entry error or may indicate the need for "
                            "clarification (e.g., part-time work, concurrent roles, or "
                            "a resume mistake that should be corrected.).",
                            fix_suggestion=(
                                "Review the overlapping date ranges and either: "
                                "(1) Correct the dates if one is a data entry error, "
                                "(2) Clarify if you held concurrent/part-time roles "
                                "(explicitly note this in the resume), or "
                                "(3) Adjust the date ranges to be non-overlapping "
                                "for clarity."
                            ),
                            example_before="Role A: Jan 2020 – Dec 2020; Role B: Jun 2020 – Dec 2021 — "
                            "6-month overlap between Role A and Role B.",
                            example_after="Role A: Jan 2020 – May 2020; Role B: Jul 2020 – Dec 2021 — "
                            "no overlap; or explicitly note: 'Concurrent part-time roles: "
                            "Company A (Jan 2020 – Dec 2020) and Company B (Jun 2020 – Dec 2021).",
                        )
                    )

    return overlaps


# ── 4. Verify chronological order (most recent first) ─────────────────────────

def verify_chronological_order(
    dates: list[dict[str, str | None]],
) -> list[Finding]:
    """Verify that date ranges are in reverse-chronological order (most recent first).

    Returns findings for any sections where the order is violated.
    """
    flags: list[Finding] = []

    # Sort dates by normalized_start descending (most recent first)
    sortable: list[dict[str, str | None]] = []
    for d in dates:
        start = d.get("normalized_start")
        if start:
            try:
                # Parse year-month for sorting
                year = int(start[:4])
                month = int(start[5:7]) if len(start) > 5 else 0
                sortable.append(
                    {
                        "raw": d.get("raw", ""),
                        "sort_key": (year, month),
                        "normalized_start": start,
                    }
                )
            except (ValueError, IndexError):
                continue

    if len(sortable) < 2:
        return flags

    # Sort descending (most recent first)
    sortable.sort(key=lambda x: x["sort_key"], reverse=True)

    # Check if the original order matches the reverse-chronological order
    # We compare the sorted order vs. what we'd expect
    # If the user provided dates in a non-standard order, flag it

    # For simplicity: check if dates are in strictly descending order
    for i in range(len(sortable) - 1):
        current_key = sortable[i]["sort_key"]
        next_key = sortable[i + 1]["sort_key"]

        # If next key is not strictly less than current key (i.e., not earlier),
        # then the order is violated
        if next_key >= current_key:
            # Find which raw texts these correspond to
            current_raw = sortable[i]["raw"]
            next_raw = sortable[i + 1]["raw"]

            flags.append(
                Finding(
                    category="ats",
                    severity="major",
                    section="ordering",
                    message="Date ranges are not in reverse-chronological order "
                    "(most recent first).",
                    why_it_matters="ATS parsers and recruiters expect experience entries "
                    "in reverse-chronological order (most recent job first). "
                    "Non-chronological ordering may cause the parser to weight your "
                    "experience incorrectly or flag your resume as poorly formatted.",
                    fix_suggestion="Reorder your experience entries so the most recent "
                    "job appears first, followed by previous jobs in descending "
                    "chronological order. If a functional format is needed for "
                    "career change, consider a hybrid approach with a 'Skills' "
                    "section front-and-center.",
                    example_before="Education (2015) — then Experience (2018–2020) — "
                    "then Experience (2015–2017) — not reverse chronological.",
                    example_after="Experience (2020–2022) — then Experience (2018–2020) — "
                    "then Education (2015) — reverse chronological.",
                )
            )

    return flags


# ── 5. Bullet/indentation consistency check ─────────────────────────────────────

def check_bullet_indentation_consistency(
    bullet_starts: list[str] | None = None,
) -> list[Finding]:
    """Flag mixed bullet styles or inconsistent indentation levels within a section.

    bullet_starts: list of strings, each is the first line of a bullet point
    as it appears in the resume text.
    """
    flags: list[Finding] = []

    if not bullet_starts or len(bullet_starts) < 2:
        return flags

    # Check for mixed bullet styles
    bullet_style_counts: dict[str, int] = {}
    for start in bullet_starts:
        # Determine the bullet style
        stripped = start.strip()
        if stripped.startswith("•") or stripped.startswith("•"):
            style = "bullet"
        elif stripped.startswith("-"):
            style = "dash"
        elif stripped.startswith("*"):
            style = "asterisk"
        else:
            # No standard bullet prefix — it's a sentence-style bullet
            style = "sentence"

        bullet_style_counts[style] = bullet_style_counts.get(style, 0) + 1

    # If we have more than one bullet style, flag it
    if len(bullet_style_counts) > 1:
        dominant = max(bullet_style_counts, key=bullet_style_counts.get)
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="formatting",
                message=f"Mixed bullet styles detected: {', '.join(f'{k} ({v})' for k, v in bullet_style_counts.items())}. "
                f"Dominant style: '{dominant}'.",
                why_it_matters="Inconsistent bullet styling can make a resume look "
                "unprofessional when parsed by ATS systems, and may indicate "
                "manual formatting that doesn't survive ATS rendering.",
                fix_suggestion="Choose one bullet style and use it consistently "
                "throughout: • (bullet), - (dash), or * (asterisk). Avoid mixing "
                "styles within the same section (e.g., don't use both • and - "
                "within the 'Skills' section or 'Work Experience' section.).",
                example_before="Mixed: '• Developed API', '- managed team', '* designed DB'",
                example_after="Consistent: '• Developed API', '• Managed team', '• Designed DB'",
            )
        )

    # Check for indentation inconsistency (lines with varying leading whitespace
    # that suggest nested sub-bullets at different levels)
    indent_levels: list[int] = []
    for start in bullet_starts:
        # Count leading whitespace / indent
        indent = len(start) - len(start.lstrip())
        indent_levels.append(indent)

    if indent_levels:
        unique_indents = set(indent_levels)
        if len(unique_indents) > 2:
            # More than 2 indent levels suggests deep nesting or inconsistent formatting
            flags.append(
                Finding(
                    category="ats",
                    severity="info",
                    section="formatting",
                    message=f"Multiple indentation levels detected ({len(unique_indents)} levels): "
                    f"{sorted(unique_indents)}. "
                    "Ensure sub-bullets are consistently indented.",
                    why_it_matters="Deep or inconsistent indentation may not render "
                    "correctly in all ATS systems, and some may flatten the hierarchy, "
                    "losing the relationship between parent and sub-items.",
                    fix_suggestion="Use a consistent indentation scheme: either no indentation "
                    "for top-level bullets, or a single increment (e.g., 2 spaces) for "
                    "sub-bullets. Avoid mixing indent levels within the same section.",
                    example_before="Mixed indentation: top-level bullets at column 0, "
                    "sub-bullets at column 2 and column 4",
                    example_after="Consistent: all top-level bullets at column 0, "
                    "sub-bullets indented 2 spaces consistently.",
                )
            )

    return flags


# ── Public API: run all formatting consistency checks ────────────────────────────

def run_all_formatting_checks(
    text: str,
    bullet_starts: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full formatting consistency check suite.

    Returns a dict with:
    - dates: list of all extracted date ranges (as dicts with raw, normalized_start, etc.)
    - format_inconsistency: Finding or None for date format inconsistency
    - employment_gaps: list of Findings for gaps > 6 months
    - overlapping_dates: list of Findings for overlapping date ranges
    - chrono_order: list of Findings for chronological order violations
    - bullet_consistency: list of Findings for bullet/indentation inconsistency
    """
    # Extract all dates from the text
    dates = extract_dates_from_text(text)

    # Run all checks
    format_inconsistency = detect_date_format_inconsistency(dates)
    employment_gaps = detect_employment_gaps(dates)
    overlapping_dates = detect_overlapping_dates(dates)
    chrono_order = verify_chronological_order(dates)
    bullet_consistency = check_bullet_indentation_consistency(bullet_starts=bullet_starts)

    return {
        "dates": dates,
        "format_inconsistency": format_inconsistency,
        "employment_gaps": employment_gaps,
        "overlapping_dates": overlapping_dates,
        "chrono_order": chrono_order,
        "bullet_consistency": bullet_consistency,
    }
