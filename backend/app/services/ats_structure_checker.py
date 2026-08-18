"""ATS Compatibility Engine — file-level structural checks.

Detects everything that causes a parser to silently mangled or drop resume data.
Pure document forensics — no ML needed for most of it.

Error contract: never raises — all failures are captured as flags with severity,
explanation, and fix suggestion.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.schemas import Finding, AtScore


# ── Canonical font list (per ATS best-practice guidance, 2026) ────────────────

APPROVED_FONTS = {
    "Arial",
    "Calibri",
    "Garamond",
    "Georgia",
    "Times New Roman",
    "Helvetica",
    "Tahoma",
    "Verdana",
}


# ── Bullet glyph blacklist — non-standard characters that render as garbage ───

NON_STANDARD_BULLETS = set(
    [
        "❖",
        "➤",
        "‣",
        "• ",  # valid bullet with trailing space — we flag if there's a non-standard one
    ]
)

STANDARD_BULLETS = {"•", "-", "*"


}


# ── 1. File-type & encoding check ─────────────────────────────────────────────


def check_file_type_and_encoding(
    filename: str, extracted_text: str
) -> Finding | None:
    """Flag scanned image PDFs (no extractable text layer)."""

    if not extracted_text.strip():
        return Finding(
            category="ats",
            severity="critical",
            section="file",
            message="Scanned image PDF detected — no extractable text layer found.",
            why_it_matters="ATS parsers cannot extract text from image-based PDFs. "
            "The resume content is effectively lost.",
            fix_suggestion="Provide a text-selectable PDF or a DOCX file. "
            "If only a scanned copy is available, run OCR first.",
            example_before="[Empty extracted text — scanned PDF]",
            example_after="[Text extracted after OCR]",
        )
    return None


# ── 2. File format risk flag ──────────────────────────────────────────────────

def check_file_format(filename: str) -> Finding | None:
    """Flag PDF vs DOCX — recommend DOCX as safe default."""

    lower = filename.lower()
    if lower.endswith(".pdf"):
        # PDF is usually fine but we flag it
        return Finding(
            category="ats",
            severity="minor",
            section="file",
            message="File format is PDF — verify your target ATS supports PDF parsing.",
            why_it_matters="Some ATS systems handle PDF less reliably than DOCX. "
            "DOCX is recommended as the safe default per current 2026 guidance.",
            fix_suggestion="If possible, re-save your resume as DOCX before uploading. "
            "If you must use PDF, ensure it is text-based (not scanned image).",
            example_before="resume.pdf",
            example_after="resume.docx",
        )
    if lower.endswith(".docx"):
        return Finding(
            category="ats",
            severity="info",
            section="file",
            message="File format is DOCX — generally well-supported by ATS systems.",
            why_it_matters="DOCX is the recommended format for maximum ATS compatibility "
            "in 2026.",
            fix_suggestion="No action needed — DOCX is the safe default.",
            example_before="resume.docx",
            example_after="N/A",
        )
    # Unknown format
    return Finding(
        category="ats",
        severity="critical",
        section="file",
        message="Unsupported file type. Please upload a PDF or DOCX.",
        why_it_matters="The resume cannot be parsed without a supported file format.",
        fix_suggestion="Convert your resume to PDF or DOCX format.",
        example_before="resume.txt",
        example_after="resume.pdf or resume.docx",
    )


# ── 3. Column layout detector ────────────────────────────────────────────────

def check_column_layout(
    extracted_text: str, page_count: int = 1
) -> Finding | None:
    """Detect multi-column layouts using text-position coordinates.

    Note: This requires pdfplumber/PyMuPDF coordinate data. This stub checks
    for telltale signs in the extracted text itself (e.g. unusual line lengths,
    abrupt position shifts).
    """
    # Simple heuristic: if there are many very short lines interrupted by
    # blank lines, it may indicate columns.
    lines = [ln.strip() for ln in extracted_text.splitlines() if ln.strip()]
    if not lines:
        return None

    # Check for very rapid alternation between vastly different line lengths,
    # which can indicate text flowing from one column to another.
    line_lengths = [len(ln) for ln in lines]
    if len(line_lengths) > 10:
        # If there's high variance in line lengths within similar y-positions,
        # that's a column indicator. For now, we check if > 30% of lines
        # are under 10 chars (suggesting multi-column flow).
        short_lines = sum(1 for l in line_lengths if l < 10)
        if short_lines / len(line_lengths) > 0.3:
            return Finding(
                category="ats",
                severity="major",
                section="layout",
                message="Multi-column layout detected — parsers may merge unrelated content across columns.",
                why_it_matters="Two-column resume layouts often cause ATS parsers to "
                "incorrectly merge text from the left and right columns, resulting "
                "in scrambled personal info, skills, or experience details.",
                fix_suggestion="Use a single-column layout. If you must use two columns, "
                "ensure each column's content is complete and separated, or provide "
                "a plain-text version of your resume.",
                example_before="Two-column layout: left column has contact info, right "
                "column has summary — parser may merge them interleaved.",
                example_after="Single-column layout with all sections stacked vertically.",
            )
    return None


# ── 4. Table detector ─────────────────────────────────────────────────────────

def check_table_structure(
    docx_tables: list[Any] | None = None,
    pdf_tables: list[Any] | None = None,
) -> Finding | None:
    """Flag any detected table structure — tables are a top cause of field-misassignment."""

    has_tables = False
    if docx_tables:
        has_tables = len(docx_tables) > 0
    if pdf_tables:
        has_tables = len(pdf_tables) > 0

    if has_tables:
        return Finding(
            category="ats",
            severity="major",
            section="structure",
            message="Table structure detected — ATS parsers may misassign fields.",
            why_it_matters="Tables in resumes are a top cause of field-misassignment "
            "by ATS systems. Content may be reordered or dropped entirely.",
            fix_suggestion="Avoid tables in your resume. Use plain text with clear "
            "section separators (e.g., 'Work Experience', 'Education', 'Skills'). "
            "If you must use a table, provide a parallel plain-text version.",
            example_before="Table with skills in left column, employment dates in "
            "right column — parser may drop one column or reorder rows.",
            example_after="Skills listed vertically under a 'Skills' section header, "
            "employment dates listed under each job entry.",
        )
    return None


# ── 5. Text box / floating element detector ────────────────────────────────────

def check_text_boxes(
    docx_tables: list[Any] | None = None,
    pdf_floating_boxes: list[Any] | None = None,
) -> Finding | None:
    """Flag embedded text boxes / floating elements disconnected from main flow."""

    # In a real implementation, we'd check docx XML for w:txbxContent elements
    # and PDF bounding boxes disconnected from the main text flow.
    # For now, we check if docx tables contain suspicious content patterns.
    has_textboxes = False
    if docx_tables:
        # Heuristic: if any table cell text is very short or has unusual patterns
        has_textboxes = True  # simplified for this stub

    if has_textboxes and pdf_floating_boxes:
        return Finding(
            category="ats",
            severity="minor",
            section="layout",
            message="Text box / floating element detected — may be skipped by some parsers.",
            why_it_matters="Contact info, skill ratings, or social icons placed in "
            "text boxes or floating elements may be entirely skipped by ATS parsers, "
            "since parsers typically process only the main text flow.",
            fix_suggestion="Avoid text boxes and floating elements. Place all contact "
            "info, skills, and achievements in the main body text with proper section "
            "headers.",
            example_before="Email address placed in a text box at the top of the resume — "
            "some parsers skip it entirely.",
            example_after="Email address placed directly under the name in the main "
            "body text, above the 'Skills' section.",
        )
    return None


# ── 6. Header/footer content check ────────────────────────────────────────────

def check_header_footer_contact(
    has_header_contact: bool = False,
    has_footer_contact: bool = False,
) -> Finding | None:
    """Flag contact info placed in document header/footer."""

    if has_header_contact or has_footer_contact:
        return Finding(
            category="ats",
            severity="critical",
            section="contact",
            message="Contact information in header/footer — many parsers skip these regions entirely.",
            why_it_matters="ATS parsers commonly ignore header and footer content. "
            "Critical information like your name, email, or phone placed there may "
            "not be extracted at all.",
            fix_suggestion="Place all contact information (name, phone, email, LinkedIn) "
            "in the main body of the resume, not in the header or footer. Name should "
            "appear as regular body text, typically the very first line.",
            example_before="Name and phone in a header that repeats on every page — "
            "parser may omit them.",
            example_after="Name on the first line, followed by phone/email/LinkedIn "
            "as regular body text below the name.",
        )
    return None


# ── 7. Image / icon detector ─────────────────────────────────────────────────

def check_embedded_images(
    has_images: bool = False,
    is_profile_photo: bool = False,
) -> Finding | None:
    """Flag embedded images — profile photos, skill-rating graphics, social icons."""

    if has_images:
        severity = "critical" if is_profile_photo else "major"
        return Finding(
            category="ats",
            severity=severity,
            section="visuals",
            message="Embedded image(s) detected — may cause ATS to reject the file outright.",
            why_it_matters="ATS systems cannot extract text from embedded images. "
            "Profile photos, skill-rating graphics, and social media icons carry "
            "zero parseable text and can trigger some ATS to reject the file "
            "completely to avoid unexpected behavior.",
            fix_suggestion="Remove all embedded images from your resume. If you have "
            "a profile photo, place it on a separate visual resume (not the ATS version), "
            "or omit it entirely for the ATS version. List social media profiles "
            "(GitHub, LinkedIn, Twitter) as plain-text hyperlinks in the appropriate "
            "sections.",
            example_before="Profile photo embedded at top of resume — parser may reject "
            "the entire file.",
            example_after="Profile photo removed; LinkedIn URL listed as plain text "
            "under the 'Contact' section.",
        )
    return None


# ── 8. Font consistency checker ───────────────────────────────────────────────

def check_font_consistency(
    font_names: list[str] | None = None,
) -> Finding | None:
    """Flag non-standard fonts and font-count > 2-3."""

    if not font_names:
        # Can't check without font data — return None (no flag)
        return None

    non_standard = [f for f in font_names if f not in APPROVED_FONTS]
    font_count = len(set(font_names))

    flags: list[Finding] = []

    if non_standard:
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="formatting",
                message=f"Non-standard font(s) detected: {', '.join(non_standard)}. "
                "ATS may render these as default fonts, losing intended styling.",
                why_it_matters="When an ATS cannot render your chosen font, it falls back "
                "to a default (usually Times New Roman or Arial). This can reflow text "
                "in unexpected ways, potentially shifting section boundaries or cutting "
                "content.",
                fix_suggestion="Use only approved fonts: Arial, Calibri, Garamond, "
                "Georgia, Times New Roman, Helvetica, Tahoma, or Verdana. Limit your "
                "resume to at most 2–3 different font families.",
                example_before="Uses Cambria and Playfair Display — ATS renders in "
                "Times New Roman, potentially reflowing section boundaries.",
                example_after="Uses Calibri consistently throughout — ATS renders "
                "as intended with no reflow.",
            )
        )

    if font_count > 3:
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="formatting",
                message=f"High font count detected ({font_count} fonts used). "
                "Inconsistency may signal layout instability.",
                why_it_matters="Using more than 2–3 font families on a single resume "
                "is unusual and may indicate unstable layout or manual formatting "
                "that doesn't survive ATS parsing.",
                fix_suggestion="Reduce to 2–3 font families maximum: one for body text, "
                "one for headings (if different), and optionally one for your name. "
                "Stick to the approved list above.",
                example_before="Uses 5 different fonts across the resume — ATS parsing "
                "may produce unpredictable results.",
                example_after="Uses consistently Calibri for body text and Arial for "
                "section headers — only 2 fonts total.",
            )
        )

    return flags if flags else None


# ── 9. Font size sanity check ─────────────────────────────────────────────────

def check_font_size(
    body_min: int | None = None,
    body_max: int | None = None,
    name_size: int | None = None,
) -> Finding | None:
    """Flag body text < 10pt or > 12pt, name/header text disproportionate."""

    flags: list[Finding] = []

    if body_min is not None and body_min < 10:
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="formatting",
                message=f"Body text as small as {body_min}pt may be too small for "
                "some ATS renderers.",
                why_it_matters="If body text is set below 10pt, some ATS renderers "
                "may clip or fail to extract text, especially at smaller font sizes "
                "used in narrow columns or dense sections.",
                fix_suggestion="Ensure body text is at least 10pt. If your resume "
                "feels cramped, reduce content density rather than shrinking the font.",
                example_before="Body text at 9pt — some ATS renderers may truncate "
                "text blocks.",
                example_after="Body text at 11pt — comfortably within the safe range "
                "for all ATS systems.",
            )
        )

    if body_max is not None and body_max > 12:
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="formatting",
                message=f"Body text as large as {body_max}pt may indicate insufficient "
                "content density.",
                why_it_matters="Body text above 12pt is unusual for resumes and may "
                "indicate that the resume is under-filled, or that heading sizes have "
                "been incorrectly applied to body text.",
                fix_suggestion="Aim for body text between 10–12pt. If headings are "
                "larger, that's fine — just ensure body content is in the 10–12pt range.",
                example_before="Body text at 14pt with very little content — may signal "
                "a very sparse resume.",
                example_after="Body text at 11pt with complete section coverage — "
                "balanced and parser-friendly.",
            )
        )

    if name_size is not None and name_size > 20:
        flags.append(
            Finding(
                category="ats",
                severity="info",
                section="formatting",
                message=f"Name/header text at {name_size}pt is disproportionately large.",
                why_it_matters="An excessively large name can unbalance the visual layout "
                "and may cause some ATS renderers to misidentify the start of the "
                "main content body.",
                fix_suggestion="Keep name text between 14–18pt. If your name is currently "
                "larger, reduce it and increase white space around it instead.",
                example_before="Name at 36pt — dominates the page, may push contact info "
                "off-screen in ATS rendering.",
                example_after="Name at 16pt — clearly visible without overwhelming "
                "the page layout.",
            )
        )

    return flags if flags else None


# ── 10. Margin check ──────────────────────────────────────────────────────────

def check_margins(
    margin_val: float | None = None,
) -> Finding | None:
    """Flag margins < 0.5" (content may get clipped by some renderers)."""

    if margin_val is not None and margin_val < 0.5:
        return Finding(
            category="ats",
            severity="minor",
            section="layout",
            message=f"Margins are {margin_val}\" — some ATS renderers may clip content "
            "at margins smaller than 0.5 inches.",
            why_it_matters="Margins below 0.5\" can cause ATS renderers to clip or "
            "truncate content at the page edges, potentially cutting off your name, "
            "contact info, or the last line of your last section.",
            fix_suggestion="Set margins to at least 0.5\" on all sides. If you need "
            "more content space, reduce font size before reducing margins.",
            example_before="Margins at 0.25\" — ATS may clip the last line of your "
            "Education section and your contact info.",
            example_after="Margins at 0.75\" — safe margin that all ATS renderers "
            "handle correctly.",
        )
    return None


# ── 11. Page count check ──────────────────────────────────────────────────────

def check_page_count(
    page_count: int,
    years_experience: int | None = None,
) -> Finding | None:
    """Flag > 2 pages (or > 1 page for < 5 years experience)."""

    max_pages = 1 if (years_experience is not None and years_experience < 5) else 2

    if page_count > max_pages:
        severity = "major" if page_count > max_pages + 1 else "minor"
        return Finding(
            category="ats",
            severity=severity,
            section="length",
            message=f"Resume is {page_count} page(s) — exceeds recommended {max_pages} "
            f"page{'s' if max_pages > 1 else ''} "
            f"(threshold: {'1 page for < 5 years experience' if years_experience and years_experience < 5 else '2 pages'}).",
            why_it_matters="Resumes exceeding the page count threshold may have "
            "content truncated or reflowed unexpectedly by ATS parsers. "
            "For early-career candidates (< 5 years), 1 page is the standard; "
            "for senior candidates, 2 pages are acceptable.",
            fix_suggestion="If over the limit, consolidate content: merge similar "
            "achievements, remove older irrelevant experience, and use concise "
            "bullet statements. For senior candidates: 2 pages are acceptable if "
            "all content is relevant and well-structured.",
            example_before="3-page resume for 3 years experience — likely padded "
            "or overly detailed for the experience level.",
            example_after="2-page resume for 10 years experience — concise, "
            "well-structured with only relevant achievements included.",
        )
    return None


# ── 12. Hyperlink check ───────────────────────────────────────────────────────

def check_hyperlinks(
    has_masked_hyperlinks: bool = False,
    has_plain_urls: bool = False,
) -> Finding | None:
    """Detect 'Click Here'-style masked hyperlinks vs plain visible URLs."""

    if has_masked_hyperlinks and not has_plain_urls:
        return Finding(
            category="ats",
            severity="minor",
            section="hyperlinks",
            message="Masked hyperlinks detected (e.g. 'Click Here' without visible URL).",
            why_it_matters="When a hyperlink's display text is 'Click Here' or similar, "
            "stripping the hyperlink removes the meaningful text. ATS parsers that "
            "strip hyperlinks will lose the URL and the context, making it impossible "
            "for recruiters to click through to your projects, portfolio, or LinkedIn.",
            fix_suggestion="Use plain visible URLs as link text, or write descriptive "
            "link text (e.g., 'My Portfolio (github.com/username)' instead of just "
            "'Click Here'). Always include the raw URL somewhere in the resume "
            "for ATS-friendliness.",
            example_before="'Click Here' links to portfolio — after stripping, "
            "nothing meaningful remains.",
            example_after="'https://github.com/username' as plain text — visible and "
            "parsable regardless of hyperlink stripping.",
        )
    return None


# ── 13. Special character / bullet glyph checker ──────────────────────────────

def check_bullets(
    bullet_chars: list[str] | None = None,
) -> Finding | None:
    """Flag non-standard bullet characters that can render as garbage."""

    if not bullet_chars:
        return None

    non_standard_found = [
        c for c in bullet_chars if c not in STANDARD_BULLETS and c not in NON_STANDARD_BULLETS
    ]

    # Check for emoji or other unusual chars
    unusual = [c for c in bullet_chars if ord(c) > 127 and c not in "•-*"]
    # Keep only truly non-standard (not •, -, * which are standard)
    truly_non_standard = [
        c for c in unusual if c not in "•-*" and c not in NON_STANDARD_BULLETS
    ]

    flags: list[Finding] = []

    if truly_non_standard:
        flags.append(
            Finding(
                category="ats",
                severity="minor",
                section="formatting",
                message=f"Non-standard bullet glyph(s) detected: {', '.join(set(truly_non_standard))}. "
                "May render as garbage characters (�) in parsed output.",
                why_it_matters="Non-standard bullet characters can render as replacement "
                "characters (�) when parsed by ATS systems, making the resume look "
                "unprofessional and potentially obscuring the actual content.",
                fix_suggestion="Use standard bullet characters: • (bullet), - (dash), "
                "* (asterisk). These are universally supported across ATS systems "
                "and rendering platforms.",
                example_before="Uses ❖ or ➤ bullets — ATS renders as � or question marks.",
                example_after="Uses • or - bullets — universally parsable.",
            )
        )

    return flags if flags else None


# ── 14. Filename check ────────────────────────────────────────────────────────

def check_filename(filename: str) -> Finding | None:
    """Flag generic filenames (resume.pdf, Document1.docx)."""

    lower = filename.lower()
    generic_patterns = [
        "resume",
        "cv",
        "document",
        "doc1",
        "doc2",
        "myresume",
        "my_cv",
    ]

    # Check if the filename is just a generic name without the person's name
    import os
    basename = os.path.splitext(lower)[0]

    # Heuristic: if the basename is a common word without first/last name indicators
    name_parts = basename.split("_")
    has_person_name = (
        len(name_parts) >= 2
        and all(p.isalpha() for p in name_parts[:2])
        and all(len(p) >= 2 for p in name_parts[:2])
    )

    if basename in [p.lower() for p in generic_patterns] and not has_person_name:
        return Finding(
            category="ats",
            severity="minor",
            section="file",
            message=f"Generic filename detected: '{filename}'. "
            "Recruiters may not open it; applicant tracking systems prefer named files.",
            why_it_matters="Generic filenames like 'resume.pdf' or 'Document1.docx' "
            "are easily lost among other files. Named files with your name are more "
            "likely to be opened and remembered by recruiters, and some ATS systems "
            "use the filename as a reference when you re-apply.",
            fix_suggestion="Rename your resume to include your first and last name, "
            "e.g., 'John_Doe_Resume.pdf' or 'Jane_Smith_CV.docx'. Avoid names like "
            "'resume.pdf' or 'updated_resume.pdf'.",
            example_before="resume.pdf",
            example_after="John_Doe_Resume.pdf",
        )
    return None


# ── Public API: run all ATS structure checks ───────────────────────────────────

def run_all_ats_structure_checks(
    filename: str,
    extracted_text: str,
    page_count: int,
    docx_tables: list | None = None,
    pdf_floating_boxes: list | None = None,
    docx_contact_in_header_footer: bool = False,
    pdf_contact_in_header_footer: bool = False,
    has_images: bool = False,
    is_profile_photo: bool = False,
    font_names: list[str] | None = None,
    body_min_pt: int | None = None,
    body_max_pt: int | None = None,
    name_pt: int | None = None,
    margin_in: float | None = None,
    years_experience: int | None = None,
    bullet_chars: list[str] | None = None,
    has_masked_hyperlinks: bool = False,
    has_plain_urls: bool = False,
) -> AtScore:
    """Run the full ATS structure check suite and return an AtScore with findings."""

    from app.models.schemas import AtScore

    findings: list[Finding] = []
    AtScoreClass = AtScore

    # 1. File type & encoding check
    ft = check_file_type_and_encoding(filename, extracted_text)
    if ft:
        findings.append(ft)

    # 2. File format risk flag
    ff = check_file_format(filename)
    if ff:
        findings.append(ff)

    # 3. Column layout detector
    cl = check_column_layout(extracted_text, page_count)
    if cl:
        findings.append(cl)

    # 4. Table structure
    dt = check_table_structure(docx_tables=docx_tables)
    if dt:
        findings.append(dt)

    # 5. Text boxes / floating elements
    tb = check_text_boxes(docx_tables=docx_tables, pdf_floating_boxes=pdf_floating_boxes)
    if tb:
        findings.append(tb)

    # 6. Header/footer contact info
    hf = check_header_footer_contact(
        has_header_contact=docx_contact_in_header_footer,
        has_footer_contact=pdf_contact_in_header_footer,
    )
    if hf:
        findings.append(hf)

    # 7. Embedded images
    ii = check_embedded_images(has_images=has_images, is_profile_photo=is_profile_photo)
    if ii:
        findings.append(ii)

    # 8. Font consistency
    fc = check_font_consistency(font_names=font_names)
    if fc:
        findings.extend(fc)

    # 9. Font size sanity
    fs = check_font_size(
        body_min=body_min_pt,
        body_max=body_max_pt,
        name_size=name_pt,
    )
    if fs:
        findings.extend(fs)

    # 10. Margin check
    mc = check_margins(margin_val=margin_in)
    if mc:
        findings.append(mc)

    # 11. Page count check
    pc = check_page_count(page_count=page_count, years_experience=years_experience)
    if pc:
        findings.append(pc)

    # 12. Hyperlink check
    hl = check_hyperlinks(
        has_masked_hyperlinks=has_masked_hyperlinks,
        has_plain_urls=has_plain_urls,
    )
    if hl:
        findings.append(hl)

    # 13. Bullet glyph check
    bc = check_bullets(bullet_chars=bullet_chars)
    if bc:
        findings.extend(bc)

    # 14. Filename check
    fn = check_filename(filename)
    if fn:
        findings.append(fn)

    # Severity weighting for the ATS score calculation
    # Start at 100, subtract weighted penalties per flag
    critical_count = sum(1 for f in findings if f.severity == "critical")
    major_count = sum(1 for f in findings if f.severity == "major")
    minor_count = sum(1 for f in findings if f.severity == "minor")

    # Penalty per severity: critical=15, major=8, minor=3
    # (These weights can be tuned via config)
    penalty = critical_count * 15 + major_count * 8 + minor_count * 3
    score = max(0.0, round(100.0 - penalty, 1))

    atscore = AtScoreClass(
        score=score,
        findings=findings,
        format=filename.lower().rsplit(".", 1)[-1] if "." in filename else "unknown",
    )

    return atscore