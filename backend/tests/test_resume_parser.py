"""Phase 1 tests for the resume parser: valid docs extract, unsupported and
corrupt inputs raise clean ValueError (mapped to HTTP 400 upstream).
"""
import io
import os
from pathlib import Path

import pytest

from app.services.resume_parser import parse_resume

FIXTURES = Path(__file__).parent / "fixtures"


def _pdf_bytes() -> bytes:
    return (FIXTURES / "sample_resume.pdf").read_bytes()


def _docx_bytes() -> bytes:
    return (FIXTURES / "sample_resume.docx").read_bytes()


def test_valid_pdf_extracts_nonempty_text():
    if not (FIXTURES / "sample_resume.pdf").exists():
        pytest.skip("sample_resume.pdf fixture not present")
    text = parse_resume("resume.pdf", _pdf_bytes())
    assert text.strip()
    assert "Python" in text


def test_valid_docx_extracts_nonempty_text():
    if not (FIXTURES / "sample_resume.docx").exists():
        pytest.skip("sample_resume.docx fixture not present")
    text = parse_resume("resume.docx", _docx_bytes())
    assert text.strip()
    assert "Python" in text


def test_unsupported_extension_raises_valueerror():
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_resume("resume.txt", b"plain text")


def test_empty_file_raises_valueerror():
    with pytest.raises(ValueError, match="empty"):
        parse_resume("resume.pdf", b"")


def test_oversized_file_raises_valueerror():
    big = b"x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="too large"):
        parse_resume("resume.pdf", big)


def test_corrupt_pdf_raises_clean_valueerror(monkeypatch):
    """Corrupt/invalid bytes must never crash the process — they surface as a
    user-presentable ValueError."""
    corrupt = b"this is absolutely not a pdf file"
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        pytest.skip("pdfplumber not installed")
    with pytest.raises(ValueError):
        parse_resume("broken.pdf", corrupt)


def test_corrupt_docx_raises_clean_valueerror():
    try:
        import docx  # noqa: F401
    except ImportError:
        pytest.skip("python-docx not installed")
    with pytest.raises(ValueError):
        parse_resume("broken.docx", b"\x00\x01not a real docx")


def test_filename_none_safe():
    with pytest.raises(ValueError, match="Unsupported file type"):
        parse_resume(None, b"data")
