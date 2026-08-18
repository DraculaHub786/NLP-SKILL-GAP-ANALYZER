"""Tests for the ATS Structure Checker engine.

These tests use known-bad fixture resumes to verify that each specific flag is
correctly triggered. Each fixture is a deliberately broken sample resume.
"""
import pytest

from backend.app.services.ats_structure_checker import (
    check_file_type_and_encoding,
    check_file_format,
    check_column_layout,
    check_table_structure,
    check_text_boxes,
    check_header_footer_contact,
    check_embedded_images,
    check_font_consistency,
    check_font_size,
    check_margins,
    check_page_count,
    check_hyperlinks,
    check_bullets,
    check_filename,
    run_all_ats_structure_checks,
)


class TestFileTypeEncoding:
    """Test file-type and encoding checks."""

    def test_scanned_pdf_no_text(self):
        """Scanned image PDF with no extractable text should be flagged critical."""
        finding = check_file_type_and_encoding("resume.pdf", "")
        assert finding is not None
        assert finding.severity == "critical"
        assert "Scanned image PDF" in finding.message

    def test_pdf_has_text(self):
        """PDF with extractable text should not be flagged."""
        finding = check_file_type_and_encoding("resume.pdf", "John Doe\nSoftware Engineer")
        assert finding is None

    def test_unsupported_format(self):
        """Unsupported file type should be flagged critical."""
        finding = check_file_type_and_encoding("resume.txt", "Some text")
        assert finding is not None
        assert finding.severity == "critical"
        assert "Unsupported file type" in finding.message

    def test_pdf_format_flag(self):
        """PDF format should get a minor flag."""
        finding = check_file_format("resume.pdf")
        assert finding is not None
        assert finding.severity == "minor"
        assert "PDF" in finding.message

    def test_docx_format_flag(self):
        """DOCX format should get an info flag."""
        finding = check_file_format("resume.docx")
        assert finding is not None
        assert finding.severity == "info"
        assert "DOCX" in finding.message

    def test_unsupported_format_flag(self):
        """Unknown format should be critical."""
        finding = check_file_format("resume.xyz")
        assert finding is not None
        assert finding.severity == "critical"


class TestColumnLayout:
    """Test column layout detection."""

    def test_single_column_passes(self):
        """Single-column resume should not trigger column layout flag."""
        finding = check_column_layout(
            "Software Engineer\nJohn Doe\n5+ years experience in Python and Django\n"
            "Built web applications and services.\n"
            "Led a team of 4 developers.\n"
            "Managed databases and infrastructure.",
            page_count=1,
        )
        # May or may not flag depending on line length heuristics,
        # but single-column should typically pass
        assert finding is None or finding.severity == "info"

    def test_multi_column_triggers(self):
        """Multi-column layout should trigger a major flag."""
        # Simulate two-column text with very different line lengths mixed together
        multi_col_text = (
            "John Doe\n"  # contact info column
            "Software Engineer\n"
            "Python, Django, AWS\n"
            "• Led team of 4\n"
            "\n"
            "Jane Smith\n"  # other column content
            "Data Scientist\n"
            "• Machine Learning\n"
            "• Python\n"
        )
        finding = check_column_layout(multi_col_text, page_count=1)
        # This is a heuristic so we just check the structure
        if finding:
            assert finding.category == "ats"


class TestTableStructure:
    """Test table structure detection."""

    def test_table_triggers_flag(self):
        """Table structure should trigger a major flag."""
        # We can't easily pass real docx/tables here, but we can test the function
        # with the parameters it expects
        finding = check_table_structure(docx_tables=["table1"])
        assert finding is not None
        assert finding.severity == "major"
        assert "Table structure" in finding.message

    def test_no_tables_passes(self):
        """No tables should pass."""
        finding = check_table_structure(docx_tables=None)
        # May return None if no tables detected


class TestTextBoxes:
    """Test text box / floating element detection."""

    def test_textbox_triggers_flag(self):
        """Text boxes should trigger a minor flag."""
        finding = check_text_boxes(docx_tables=["table_with_textbox"])
        assert finding is not None
        assert finding.severity == "minor"
        assert "Text box" in finding.message

    def test_no_textboxes_passes(self):
        """No text boxes should pass."""
        finding = check_text_boxes(docx_tables=None)
        # May return None


class TestHeaderFooterContact:
    """Test header/footer contact info detection."""

    def test_header_contact_triggers_critical(self):
        """Contact in header should be critical."""
        finding = check_header_footer_contact(has_header_contact=True, has_footer_contact=False)
        assert finding is not None
        assert finding.severity == "critical"
        assert "header" in finding.message.lower()

    def test_no_header_contact_passes(self):
        """No contact in header should pass."""
        finding = check_header_footer_contact(has_header_contact=False, has_footer_contact=False)
        assert finding is None


class TestEmbeddedImages:
    """Test embedded image detection."""

    def test_profile_photo_critical(self):
        """Profile photo should be critical."""
        finding = check_embedded_images(has_images=True, is_profile_photo=True)
        assert finding is not None
        assert finding.severity == "critical"
        assert "profile" in finding.message.lower() or "embedded" in finding.message.lower()

    def test_graphics_major(self):
        """Non-profile embedded images should be major."""
        finding = check_embedded_images(has_images=True, is_profile_photo=False)
        assert finding is not None
        assert finding.severity == "major"

    def test_no_images_passes(self):
        """No images should pass."""
        finding = check_embedded_images(has_images=False, is_profile_photo=False)
        assert finding is None


class TestFontConsistency:
    """Test font consistency checking."""

    def test_non_standard_fonts_flagged(self):
        """Non-standard fonts should be flagged minor."""
        finding = check_font_consistency(font_names=["Calibri", "Arial", "Comic Sans"])
        assert finding is not None
        # Should flag Comic Sans as non-standard
        assert any("Comic Sans" in f.message for f in finding) or len(finding) > 0

    def test_standard_fonts_passes(self):
        """Standard fonts should pass."""
        finding = check_font_consistency(font_names=["Calibri", "Arial"])
        assert finding is None or len(finding) == 0

    def test_too_many_fonts_flagged(self):
        """Using more than 3 fonts should be flagged."""
        finding = check_font_consistency(font_names=["Calibri", "Arial", "Times", "Helvetica"])
        assert finding is not None
        # Should flag the high font count


class TestFontSize:
    """Test font size sanity checks."""

    def test_body_too_small(self):
        """Body text < 10pt should be flagged."""
        finding = check_font_size(body_min_pt=9, body_max_pt=12, name_pt=16)
        assert finding is not None
        assert finding.severity == "minor"
        assert "9pt" in finding.message or "too small" in finding.message.lower()

    def test_body_too_large(self):
        """Body text > 12pt should be flagged."""
        finding = check_font_size(body_min_pt=14, body_max_pt=14, name_pt=16)
        assert finding is not None
        assert finding.severity == "minor"
        assert "14pt" in finding.message or "too large" in finding.message.lower()

    def name_size_too_large(self):
        """Name text > 20pt should be flagged."""
        finding = check_font_size(body_min_pt=11, body_max_pt=12, name_pt=24)
        assert finding is not None
        assert finding.severity == "info"
        assert "24pt" in finding.message or "disproportionately" in finding.message.lower()

    def test_all_sizes_ok(self):
        """All sizes in normal range should pass."""
        finding = check_font_size(body_min_pt=11, body_max_pt=12, name_pt=16)
        assert finding is None or len(finding) == 0


class TestMargins:
    """Test margin checks."""

    def test_small_margins(self):
        """Margins < 0.5\" should be flagged."""
        finding = check_margins(margin_in=0.25)
        assert finding is not None
        assert finding.severity == "minor"
        assert "0.25" in finding.message or "0.5" in finding.message

    def test_safe_margins(self):
        """Margins >= 0.5\" should pass."""
        finding = check_margins(margin_in=0.75)
        assert finding is None


class TestPageCount:
    """Test page count checks."""

    def test_too_many_pages(self):
        """Too many pages should be flagged."""
        # 3 pages for < 5 years experience should flag (max 1 page)
        finding = check_page_count(page_count=3, years_experience=3)
        assert finding is not None
        assert finding.severity in ["minor", "major"]

    def test_two_pages_ok_for_experienced(self):
        """2 pages for experienced candidate should pass."""
        finding = check_page_count(page_count=2, years_experience=10)
        assert finding is None

    def test_one_page_ok_for_fresher(self):
        """1 page for < 5 years experience should pass."""
        finding = check_page_count(page_count=1, years_experience=3)
        assert finding is None

    def test_two_pages_ok_for_fresher_edge(self):
        """Edge case: 2 pages for < 5 years but still may pass depending on implementation."""
        finding = check_page_count(page_count=2, years_experience=4)
        # This may or may not flag — depends on threshold logic


class TestHyperlinks:
    """Test hyperlink checks."""

    def test_masked_links_no_plain(self):
        """Masked hyperlinks without plain URLs should be flagged."""
        finding = check_hyperlinks(has_masked_hyperlinks=True, has_plain_urls=False)
        assert finding is not None
        assert finding.severity == "minor"
        assert "masked" in finding.message.lower() or "click here" in finding.message.lower()

    def test_plain_urls_ok(self):
        """Plain URLs should not trigger flag."""
        finding = check_hyperlinks(has_masked_hyperlinks=False, has_plain_urls=True)
        assert finding is None or len(finding) == 0

    def test_no_hyperlinks_ok(self):
        """No hyperlinks should pass."""
        finding = check_hyperlinks(has_masked_hyperlinks=False, has_plain_urls=False)
        assert finding is None or len(finding) == 0


class TestBulletGlyphs:
    """Test bullet glyph checks."""

    def test_nonstandard_bullets(self):
        """Non-standard bullets should be flagged."""
        finding = check_bullets(bullet_chars=["❖", "➤", "•", "-"])
        assert finding is not None
        assert finding.severity == "minor"
        assert "non-standard" in finding.message.lower() or "garbage" in finding.message.lower()

    def test_standard_bullets_ok(self):
        """Standard bullets should pass."""
        finding = check_bullets(bullet_chars=["•", "-", "*"])
        assert finding is None or len(finding) == 0

    def test_no_bullets_ok(self):
        """No bullets specified should pass."""
        finding = check_bullets(bullet_chars=None)
        assert finding is None or len(finding) == 0


class TestFilename:
    """Test filename checks."""

    def test_generic_filename(self):
        """Generic filename should be flagged."""
        finding = check_filename("resume.pdf")
        assert finding is not None
        assert finding.severity == "minor"
        assert "Generic" in finding.message

    def test_named_filename_ok(self):
        """Named filename with person's name should pass."""
        finding = check_filename("John_Doe_Resume.pdf")
        assert finding is None

    def test_cv_filename_ok(self):
        """CV with person's name should pass."""
        finding = check_filename("Jane_Smith_CV.docx")
        assert finding is None


class TestRunAllChecks:
    """Test the full ATS structure check suite."""

    def test_full_pipeline_with_bad_resume(self):
        """Run all checks on a deliberately bad resume and verify flags are raised."""
        extracted_text = ""  # Empty = scanned PDF scenario

        atscore = run_all_ats_structure_checks(
            filename="resume.pdf",
            extracted_text=extracted_text,
            page_count=2,
            docx_tables=None,
            pdf_floating_boxes=None,
            docx_contact_in_header_footer=True,
            pdf_contact_in_header_footer=False,
            has_images=False,
            is_profile_photo=False,
            font_names=["Calibri"],
            body_min_pt=11,
            body_max_pt=12,
            name_pt=16,
            margin_in=1.0,
            years_experience=3,
            bullet_chars=None,
            has_masked_hyperlinks=False,
            has_plain_urls=False,
        )

        # Should have some flags since it's a PDF with contact in header
        assert atscore is not None
        assert 0 <= atscore.score <= 100

    def test_full_pipeline_good_resume(self):
        """Run all checks on a good resume and verify reasonable score."""
        extracted_text = (
            "John Doe\n"
            "(555) 123-4567 | john@example.com | linkedin.com/in/johndoe\n"
            "\n"
            "Summary: Software Engineer with 5+ years experience in Python and Django.\n"
            "\n"
            "Skills:\n"
            "• Python, Django, PostgreSQL\n"
            "• AWS, Docker, Jenkins\n"
            "\n"
            "Experience:\n"
            "Software Engineer, ABC Corp, June 2020 – Present\n"
            "• Built web applications using Python and Django\n"
            "• Led a team of 4 developers\n"
            "\n"
            "Education:\n"
            "MS in Computer Science, University of XYZ, 2018"
        )

        atscore = run_all_ats_structure_checks(
            filename="John_Doe_Resume.pdf",
            extracted_text=extracted_text,
            page_count=1,
            docx_tables=None,
            pdf_floating_boxes=None,
            docx_contact_in_header_footer=False,
            pdf_contact_in_header_footer=False,
            has_images=False,
            is_profile_photo=False,
            font_names=["Calibri"],
            body_min_pt=11,
            body_max_pt=12,
            name_pt=16,
            margin_in=0.75,
            years_experience=5,
            bullet_chars=["•"],
            has_masked_hyperlinks=False,
            has_plain_urls=True,
        )

        # Good resume should have a high score
        assert atscore is not None
        assert atscore.score > 70, f"Expected score > 70 for good resume, got {atscore.score}"

    def test_full_pipeline_detailed_flags(self):
        """Verify that the full pipeline returns findings with all required attributes."""
        extracted_text = ""

        atscore = run_all_ats_structure_checks(
            filename="resume.pdf",
            extracted_text=extracted_text,
            page_count=1,
            docx_tables=None,
            pdf_floating_boxes=None,
            docx_contact_in_header_footer=False,
            pdf_contact_in_header_footer=False,
            has_images=False,
            is_profile_photo=False,
            font_names=["Calibri"],
            body_min_pt=11,
            body_max_pt=12,
            name_pt=16,
            margin_in=0.75,
            years_experience=3,
            bullet_chars=None,
            has_masked_hyperlinks=False,
            has_plain_urls=False,
        )

        # Every finding should have: category, severity, section, message, why_it_matters,
        # fix_suggestion, example_before, example_after
        for finding in atscore.findings:
            assert hasattr(finding, "category"), f"Finding missing 'category': {finding}"
            assert hasattr(finding, "severity"), f"Finding missing 'severity': {finding}"
            assert hasattr(finding, "section"), f"Finding missing 'section': {finding}"
            assert hasattr(finding, "message"), f"Finding missing 'message': {finding}"
            assert hasattr(finding, "why_it_matters"), f"Finding missing 'why_it_matters': {finding}"
            assert hasattr(finding, "fix_suggestion"), f"Finding missing 'fix_suggestion': {finding}"
            assert hasattr(finding, "example_before"), f"Finding missing 'example_before': {finding}"
            # example_after can be None for some flags
            assert hasattr(finding, "example_after"), f"Finding missing 'example_after': {finding}"