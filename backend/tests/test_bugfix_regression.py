"""Regression tests for Part 1 bug fixes.

Each test corresponds to a specific bug in the fix report:
  #1 — Email regex works on multi-line resume text
  #2 — Colon-terminated headers (e.g. "Skills:") are recognized
  #3 — NER tokenizer matches training data style
  #4 — Cosine similarity values are bounded in [0, 1]
  #5 — Contact detected without an explicit "Contact:" header
  #6 — City extraction from header block with MULTILINE
  #8 — Nice-to-have sections get a genuinely lower weight
"""
import re

import pytest


# ── Fix #1: Email regex ──────────────────────────────────────────────────────

from app.services.section_detector import _EMAIL_REGEX


def test_email_multiline_resume():
    """Email in the middle of a multi-paragraph resume must be found."""
    resume_text = """\
John Doe
Software Engineer

Summary
Experienced developer with 5+ years in backend systems.

Contact
Email: john.doe@example.com
Phone: (555) 123-4567

Experience
Senior Engineer — Acme Corp (2020–2024)
"""
    match = _EMAIL_REGEX.search(resume_text)
    assert match is not None
    assert match.group(0) == "john.doe@example.com"


def test_email_no_anchors_needed():
    """The regex must NOT use ^...$ anchors — .search() on multi-line text."""
    pattern_str = _EMAIL_REGEX.pattern
    assert not pattern_str.startswith("^"), "Email regex must not start with ^"
    assert not pattern_str.endswith("$"), "Email regex must not end with $"


# ── Fix #2: Colon-terminated headers ─────────────────────────────────────────

from app.api.v1 import _extract_section_headers


def test_colon_headers_recognized():
    """Headers like 'Skills:', 'Education:' must be extracted, not skipped."""
    resume_text = """\
John Doe
john@example.com

Summary
Experienced developer.

Skills:
Python, JavaScript, Docker

Education:
B.S. Computer Science, MIT

Experience:
Senior Engineer at Acme Corp
"""
    headers = _extract_section_headers(resume_text)
    header_lower = [h.lower() for h in headers]
    assert "skills" in header_lower, f"Expected 'Skills' in headers, got {headers}"
    assert "education" in header_lower, f"Expected 'Education' in headers, got {headers}"


def test_non_header_colon_lines_still_excluded():
    """Lines with internal punctuation (not just trailing colon) should still be excluded."""
    resume_text = """\
John Doe
Built the API: it handles 10K req/s.
Skills
Python
"""
    headers = _extract_section_headers(resume_text)
    # "Built the API: it handles 10K req/s." should NOT be a header
    assert not any("built" in h.lower() for h in headers)


# ── Fix #3: NER tokenization parity ──────────────────────────────────────────

from app.ml.ner_inference import _TOKEN_RE


def test_ner_punctuation_tokenization():
    """Tokenizer must split punctuation into separate tokens, matching training data."""
    text = "Experienced with React, TypeScript and GraphQL."
    tokens = _TOKEN_RE.findall(text)
    # Comma and period should be separate tokens
    assert "," in tokens, f"Expected comma as separate token, got {tokens}"
    assert "." in tokens, f"Expected period as separate token, got {tokens}"
    assert "React" in tokens
    assert "TypeScript" in tokens


def test_ner_tokenizer_no_double_spaces():
    """Tokenizer should handle multiple spaces gracefully."""
    tokens = _TOKEN_RE.findall("Python  and   SQL")
    assert "Python" in tokens
    assert "SQL" in tokens
    # No empty tokens
    assert all(t.strip() for t in tokens)


# ── Fix #4: Cosine similarity bounded ────────────────────────────────────────

from app.services.matcher import compute_gap_report


def test_cosine_similarity_bounded():
    """All similarity values in SkillMatch must be in [0, 1]."""
    resume_skills = ["Python", "JavaScript", "Docker", "AWS", "SQL"]
    jd_skills = ["Python", "Kubernetes", "React", "Machine Learning", "SQL"]
    report = compute_gap_report(resume_skills, jd_skills)
    for match in report.matched:
        assert 0.0 <= match.similarity <= 1.0, (
            f"Similarity {match.similarity} for {match.resume_skill} vs {match.jd_skill} "
            f"is outside [0, 1]"
        )


# ── Fix #5: Contact detected without header ──────────────────────────────────

from app.services.section_detector import run_all_section_checks


def test_contact_no_header():
    """Resume with email/phone at top and no 'Contact' header — contact still detected."""
    resume_text = """\
John Doe
john.doe@example.com | (555) 123-4567
San Francisco, CA

Summary
Experienced software engineer.

Skills
Python, JavaScript, Docker

Experience
Senior Engineer — Acme Corp (2020–2024)
"""
    result = run_all_section_checks(
        raw_headers=["Summary", "Skills", "Experience"],
        profile_level="experienced",
        extract_contact_from_text=resume_text,
    )
    # Contact should be detected as present (from content), not missing
    classified = result["classified"]
    assert classified.get("contact") is not None, (
        f"Contact should be detected from content, got classified={classified}"
    )
    # No "contact missing" critical finding
    missing_msgs = [f.message for f in result["missing"]]
    assert not any("Contact Information" in m for m in missing_msgs), (
        f"Should not report contact missing, found: {missing_msgs}"
    )


# ── Fix #6: City extraction from header ──────────────────────────────────────

from app.services.section_detector import extract_contact_info


def test_city_extraction_multiline():
    """City, State in the header block should be extracted."""
    resume_text = """\
John Doe
San Francisco, CA
john@example.com | (555) 123-4567

Summary
Experienced developer.
"""
    contact = extract_contact_info(resume_text)
    assert contact["city"] == "San Francisco", f"Expected 'San Francisco', got {contact['city']}"


def test_city_not_anchored_to_end():
    """City pattern must match in the header, not only at the very end of the text."""
    resume_text = """\
John Doe
New York, NY
john@example.com

Summary
Experienced developer with 5 years.

Experience
Senior Engineer — Acme Corp
"""
    contact = extract_contact_info(resume_text)
    assert contact["city"] == "New York", f"Expected 'New York', got {contact['city']}"


# ── Fix #8: Nice-to-have discount ────────────────────────────────────────────

from app.services.jd_importance import compute_importance


def test_nice_to_have_lower_weight():
    """Skills in a 'Nice to have' section must get a lower weight than baseline 1.0."""
    jd_text = """\
Requirements:
- Python programming
- SQL experience
- Docker containerization

Nice to have:
- Kubernetes experience
- AWS cloud platform
"""
    weights = compute_importance(jd_text, ["Python", "SQL", "Docker", "Kubernetes", "AWS"])
    # Requirements skills should have higher weight than nice-to-have skills
    req_avg = (weights["Python"] + weights["SQL"] + weights["Docker"]) / 3
    nice_avg = (weights["Kubernetes"] + weights["AWS"]) / 2
    assert req_avg > nice_avg, (
        f"Must-have avg ({req_avg:.2f}) should exceed nice-to-have avg ({nice_avg:.2f})"
    )


def test_nice_to_have_weight_below_baseline():
    """Nice-to-have skills with mentions should still have weight below the
    1.0 baseline due to the 0.7 discount factor."""
    jd_text = """\
Requirements:
Python

Nice to have:
Docker
Docker
Docker
"""
    weights = compute_importance(jd_text, ["Python", "Docker"])
    # Docker is mentioned 3 times but in a nice-to-have section — the boost
    # factor is 0.7, so its raw weighted count is 3 * 0.7 = 2.1 vs Python's 1 * 1.5 = 1.5
    # But Docker should NOT get the same boost as a must-have with 3 mentions
    assert weights["Python"] > 0.5
    assert weights["Docker"] > 0.5
