"""Section & Structure Detection Engine.

Detects presence/absence of required sections, section ordering, duplicate/conflicting
sections, and contact-info extraction & validation.

Mapping of section header aliases is maintained as a JSON config
(section_header_aliases.json), not hardcoded in logic.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.schemas import Finding

# ── Load section header aliases from JSON config ───────────────────────────────

_ALIASES_PATH = Path(__file__).parent.parent / "ml" / "section_header_aliases.json"

try:
    with open(_ALIASES_PATH, encoding="utf-8") as f:
        _ALIASES: dict[str, str] = json.load(f)
except FileNotFoundError:
    _ALIASES = {}
    print(f"Warning: {_ALIASES_PATH} not found — using empty alias mapping.")
except json.JSONDecodeError as exc:
    _ALIASES = {}
    print(f"Warning: {_ALIASES_PATH} has invalid JSON: {exc}")


def _canonical_header(raw: str) -> str | None:
    """Map a raw header text to its canonical section name using the alias config.

    Aliases are loaded from section_header_aliases.json. Each mapping goes from
    a variant spelling/phrasing to the canonical name used internally.

    Examples:
        "Professional Experience" -> "experience"
        "Employment History" -> "experience"
        "Work History" -> "experience"
        "Education Background" -> "education"
    """
    lower = raw.strip().lower()
    # Direct lookup
    if lower in _ALIASES:
        return _ALIASES[lower]
    # Fuzzy: try matching substrings
    for alias, canonical in _ALIASES.items():
        if alias.lower() in lower or lower in alias.lower():
            return canonical
    # Exact word-by-word match on the canonical side
    return None


# ── Required sections in parser-safe order ─────────────────────────────────────

# The order that most ATS parsers expect: Contact → Summary → Skills → Experience → Education → Certifications
PARSER_SAFE_ORDER = [
    "contact",
    "summary",
    "skills",
    "experience",
    "education",
    "certifications",
]


# ── 1. Section header classifier ───────────────────────────────────────────────

def classify_sections(
    raw_headers: list[str],
) -> dict[str, str | None]:
    """Classify each raw header into its canonical section name.

    Returns a dict mapping canonical section name -> raw header text that matched,
    with None for any headers that don't match a known section.
    """
    classified: dict[str, str | None] = {}
    for canonical in PARSER_SAFE_ORDER:
        classified[canonical] = None

    for raw in raw_headers:
        canonical = _canonical_header(raw)
        if canonical and canonical in classified:
            # Keep the first match for each canonical section
            if classified[canonical] is None:
                classified[canonical] = raw
        elif canonical is None:
            # Unknown header — track it but don't assign to a known section
            pass

    return classified


# ── 2. Detect presence/absence of required sections ─────────────────────────────

def detect_missing_sections(
    classified: dict[str, str | None],
    profile_level: str = "experienced",  # "newgrad" or "experienced"
) -> list[Finding]:
    """Flag required sections that are missing.

    Contact Info missing = critical
    Summary missing = minor (but for senior roles, becomes major)
    """
    flags: list[Finding] = []

    # Contact Info is always required
    if classified.get("contact") is None:
        flags.append(
            Finding(
                category="ats",
                severity="critical",
                section="contact",
                message="Contact Information section is missing.",
                why_it_matters="Without a Contact Information section, the ATS cannot "
                "extract your name, phone, email, or location. Recruiters cannot reach "
                "you automatically — this is the most critical parsing failure.",
                fix_suggestion="Add a Contact Information section as the very first "
                "section of your resume, including: full name, phone number, email "
                "address, and LinkedIn profile URL (as plain text).",
                example_before="[No contact section — parser finds no name/phone/email]",
                example_after="Contact: John Doe | (555) 123-4567 | john@example.com | "
                "linkedin.com/in/johndoe",
            )
        )

    # Summary/Objective — minor for experienced, but check for newgrads
    is_newgrad = profile_level == "newgrad"
    summary_missing = classified.get("summary") is None and not is_newgrad

    if summary_missing:
        # For experienced candidates, flag as minor (can be compensated by strong
        # experience section). For newgrads, we still flag but note it's expected
        # in some cases.
        severity = "minor" if not is_newgrad else "info"
        flags.append(
            Finding(
                category="ats",
                severity=severity,
                section="summary",
                message="Summary/Objective section is missing.",
                why_it_matters="A summary or objective gives the ATS and human recruiter "
                "a quick snapshot of your value proposition. Without one, the parser "
                "must infer your goals from the experience section alone.",
                fix_suggestion="Add a 2–3 sentence summary at the top of your resume, "
                "highlighting: years of experience, key skills, and one major "
                "achievement. For new grads: use an objective stating your career goal "
                "and target role type.",
                example_before="[No summary — resume starts directly with Experience]",
                example_after="Summary: 5+ years experience in software engineering "
                "specializing in Python, system design, and team leadership. Led a "
                "team of 4 to deliver a microservice platform processing 10K requests/"
                "day.",
            )
        )

    # Skills section — always check
    if classified.get("skills") is None:
        flags.append(
            Finding(
                category="ats",
                severity="critical",
                section="skills",
                message="Skills section is missing.",
                why_it_matters="The Skills section is how ATS systems index your technical "
                "and soft skills for matching against job descriptions. Without it, you "
                "will not match on skill-based queries regardless of how relevant your "
                "experience is.",
                fix_suggestion="Add a Skills section listing your technical skills, "
                "languages, frameworks, tools, and certifications. Group them logically "
                "(e.g., 'Programming Languages', 'Frameworks/Tools', 'Databases').",
                example_before="[No skills section — all skills are only mentioned in "
                "experience bullets]",
                example_after="Skills:\nProgramming: Python, JavaScript, SQL\n"
                "Tools: Git, Docker, Jenkins\nDatabases: PostgreSQL, MongoDB\n"
                "Certifications: AWS Solutions Architect Associate",
            )
        )

    return flags


# ── 3. Detect section ordering ─────────────────────────────────────────────────

def detect_section_ordering(
    classified: dict[str, str | None],
    profile_level: str = "experienced",
) -> list[Finding]:
    """Flag major deviations from parser-safe section ordering.

    Education before Experience is fine for new grads but usually wrong for
    experienced candidates — make this seniority-aware.
    """
    flags: list[Finding] = []

    # Find the positions of sections that are present
    present_sections = {
        k: v for k, v in classified.items() if v is not None and k in PARSER_SAFE_ORDER
    }

    if not present_sections:
        return flags  # Can't order nothing

    # Get the parser-safe order indices for present sections
    try:
        indices = [
            PARSER_SAFE_ORDER.index(sec) for sec in present_sections.keys()
        ]
    except ValueError:
        # Some section not in our standard list — can't order
        return flags

    # Check for major deviations
    # For experienced candidates: Education should not come before Experience
    # unless it's a new grad scenario
    if profile_level == "experienced":
        exp_idx = indices.index(PARSER_SAFE_ORDER.index("experience")) if "experience" in [PARSER_SAFE_ORDER[i] for i in indices] else -1
        edu_idx = indices.index(PARSER_SAFE_ORDER.index("education")) if "education" in [PARSER_SAFE_ORDER[i] for i in indices] else -1

        if edu_idx > -1 and exp_idx > -1 and edu_idx < exp_idx:
            # Education comes before Experience for an experienced candidate
            flags.append(
                Finding(
                    category="ats",
                    severity="major",
                    section="ordering",
                    message="Education section appears before Experience section — "
                    "unusual for experienced candidates.",
                    why_it_matters="For candidates with work experience, the reverse-"
                    "chronological format expects Experience before Education. "
                    "Placing Education first may cause the ATS to weight your "
                    "education more heavily than your professional experience, "
                    "which is typically not the signal you want to send.",
                    fix_suggestion="Reorder your resume so Experience comes before "
                    "Education, unless you are a new graduate (within 1 year of "
                    "completion). In that case, Education before Experience is fine.",
                    example_before="Education (Degree, University) — then Experience "
                    "(Job titles and dates)",
                    example_after="Experience (Job titles and dates) — then Education "
                    "(Degree, University)",
                )
            )

    # General: check for any ordering that skips required intermediate sections
    # e.g., going from Contact straight to Experience, skipping Summary and Skills
    sorted_indices = sorted(indices)
    for i in range(len(sorted_indices) - 1):
        gap = sorted_indices[i + 1] - sorted_indices[i]
        if gap > 1:
            # There's a gap in the expected order
            # Map indices back to section names
            left_sec = PARSER_SAFE_ORDER[sorted_indices[i]]
            right_sec = PARSER_SAFE_ORDER[sorted_indices[i + 1]]
            # Check if there's a mandatory section between them
            left_pos = PARSER_SAFE_ORDER.index(left_sec)
            right_pos = PARSER_SAFE_ORDER.index(right_sec)
            mandatory_between = [
                PARSER_SAFE_ORDER[j]
                for j in range(left_pos + 1, right_pos)
                if PARSER_SAFE_ORDER[j] not in classified or classified[PARSER_SAFE_ORDER[j]] is None
            ]
            if mandatory_between and profile_level == "experienced":
                flags.append(
                    Finding(
                        category="ats",
                        severity="minor",
                        section="ordering",
                        message=f"Section ordering skips mandatory section(s): "
                        f"{', '.join(mandatory_between)} between {left_sec} and {right_sec}.",
                        why_it_matters="ATS parsers typically expect sections in a specific "
                        "order. Skipping mandatory sections may cause certain content to "
                        "be weighted less heavily or even dropped during parsing.",
                        fix_suggestion="Reorder sections to follow the parser-safe order: "
                        "Contact → Summary → Skills → Experience → Education → "
                        "Certifications. If a section is not applicable, note why "
                        "in a comment or cover letter.",
                        example_before="Contact → Experience (skipping Summary and Skills)",
                        example_after="Contact → Summary → Skills → Experience → Education",
                    )
                )

    return flags


# ── 4. Detect duplicate or conflicting sections ─────────────────────────────────

def detect_duplicate_sections(
    classified: dict[str, str | None],
) -> list[Finding]:
    """Flag duplicate or conflicting sections (e.g. two 'Skills' sections)."""
    flags: list[Finding] = []

    # Count occurrences of each canonical section
    section_counts: dict[str, int] = {}
    for canonical, raw in classified.items():
        if raw is not None and canonical in section_counts:
            section_counts[canonical] += 1
        elif raw is not None:
            section_counts[canonical] = 1

    # Check for duplicates
    for canonical, count in section_counts.items():
        if count > 1:
            flags.append(
                Finding(
                    category="ats",
                    severity="major",
                    section="duplicates",
                    message=f"Duplicate section detected: '{canonical}' appears {count} time(s).",
                    why_it_matters="Duplicate sections can confuse ATS parsers. Content may "
                    "be merged, dropped, or assigned to the wrong field when the same "
                    "section header appears multiple times.",
                    fix_suggestion="Consolidate duplicate sections into one. If you have "
                    "content that logically belongs in the same category (e.g., two "
                    "'Skills' sections), merge them into a single, comprehensive section.",
                    example_before="Two 'Skills' sections — first lists programming languages, "
                    "second lists software tools — parser may merge or drop one.",
                    example_after="Single comprehensive 'Skills' section with all "
                    "programming languages, tools, and certifications listed.",
                )
            )

    return flags


# ── 5. Contact-info extraction & validation ─────────────────────────────────────

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_REGEX = re.compile(r"(\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_LINKEDIN_REGEX = re.compile(r"linkedin\.com/in/[\w-]+")


_CITY_LINE = re.compile(r"^([A-Za-z][A-Za-z ]{1,30}),\s*([A-Za-z]{2,})\s*$", re.MULTILINE)


def has_contact_block(text: str, lines_to_scan: int = 12) -> bool:
    """A resume is considered to have contact info if an email OR phone
    appears anywhere in the first N lines — header optional."""
    head = "\n".join(text.splitlines()[:lines_to_scan])
    return bool(_EMAIL_REGEX.search(head) or _PHONE_REGEX.search(head))


def extract_contact_info(
    text: str,
) -> dict[str, str | None]:
    """Extract and validate contact info from resume text.

    Returns a dict with email, phone, linkedin, and city/region if found.
    """
    contact: dict[str, str | None] = {
        "email": None,
        "phone": None,
        "linkedin": None,
        "city": None,
    }

    # Extract email
    email_match = _EMAIL_REGEX.search(text)
    if email_match:
        contact["email"] = email_match.group(0)

    # Extract phone
    phone_match = _PHONE_REGEX.search(text)
    if phone_match:
        contact["phone"] = phone_match.group(0)

    # Extract LinkedIn
    linkedin_match = _LINKEDIN_REGEX.search(text)
    if linkedin_match:
        contact["linkedin"] = linkedin_match.group(0)

    # Extract city/region from the first ~12 lines (header block) only,
    # using MULTILINE mode so ^ and $ match per-line.
    head = "\n".join(text.splitlines()[:12])
    city_match = _CITY_LINE.search(head)
    if city_match:
        contact["city"] = city_match.group(1).strip()

    return contact


def validate_contact_info(
    contact: dict[str, str | None],
) -> list[Finding]:
    """Validate extracted contact info and return flags for issues."""
    flags: list[Finding] = []

    if not contact["email"]:
        flags.append(
            Finding(
                category="ats",
                severity="critical",
                section="contact",
                message="No valid email address found in resume.",
                why_it_matters="Email is the primary way recruiters contact candidates "
                "after initial ATS screening. Without a valid email, you will not "
                "receive interview invitations through automated systems.",
                fix_suggestion="Add a valid email address to your Contact Information "
                "section. Ensure it is current and that you check it regularly.",
                example_before="[No email found]",
                example_after="john.doe@example.com",
            )
        )

    if not contact["phone"]:
        flags.append(
            Finding(
                category="ats",
                severity="major",
                section="contact",
                message="No phone number found in resume.",
                why_it_matters="While email is preferred, many recruiters still call "
                "candidates. A missing phone number limits contact methods.",
                fix_suggestion="Add a phone number to your Contact Information section "
                "in a standard format: (555) 123-4567 or 555.123.4567.",
                example_before="[No phone found]",
                example_after="(555) 123-4567",
            )
        )

    if not contact["linkedin"]:
        # Not critical, but a warning
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="contact",
                message="No LinkedIn profile URL found in resume.",
                why_it_matters="LinkedIn profiles provide verified, detailed information "
                "about your background that complement the resume. Many recruiters "
                "search LinkedIn directly after initial resume screening.",
                fix_suggestion="Add your LinkedIn profile URL (e.g., "
                "linkedin.com/in/johndoe) to your Contact Information section.",
                example_before="[No LinkedIn found]",
                example_after="linkedin.com/in/johndoe",
            )
        )

    if not contact["city"] and not contact["phone"] and not contact["email"]:
        # Very minimal — just flag that we couldn't extract any contact info at all
        pass

    return flags


# ── Public API: run all section detection checks ────────────────────────────────

def run_all_section_checks(
    raw_headers: list[str],
    classified: dict[str, str | None] | None = None,
    profile_level: str = "experienced",
    extract_contact_from_text: str = "",
) -> dict[str, Any]:
    """Run the full section detection suite and return structured results.

    Returns a dict with:
    - classified: dict mapping canonical section name -> raw header text (or None)
    - missing: list of Findings for missing required sections
    - ordering: list of Findings for ordering issues
    - duplicates: list of Findings for duplicate sections
    - contact_validation: list of Findings for contact info issues
    - contact_extracted: dict with extracted contact info (email, phone, linkedin, city)
    """
    if classified is None:
        classified = classify_sections(raw_headers)

    # Fix #5: If no literal "Contact" header was found but contact info (email/phone)
    # exists in the first N lines of the resume, treat contact as present to avoid
    # false critical findings on resumes that don't use a "Contact:" header.
    if classified.get("contact") is None and has_contact_block(extract_contact_from_text):
        classified["contact"] = "(detected from content — no explicit header)"

    missing = detect_missing_sections(classified, profile_level=profile_level)
    ordering = detect_section_ordering(classified, profile_level=profile_level)
    duplicates = detect_duplicate_sections(classified)
    contact = extract_contact_info(extract_contact_from_text)
    contact_validation = validate_contact_info(contact)

    return {
        "classified": classified,
        "missing": missing,
        "ordering": ordering,
        "duplicates": duplicates,
        "contact_validation": contact_validation,
        "contact_extracted": contact,
    }
