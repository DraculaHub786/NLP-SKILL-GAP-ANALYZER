"""Parses resume files (PDF/DOCX) into plain text, in-memory only.

No file is ever written to disk: everything happens on the UploadFile's
in-memory buffer / spooled temp file, and nothing outlives the request.
"""
import io

import pdfplumber
from docx import Document


def parse_pdf(file_bytes: bytes) -> str:
    text_chunks: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    text = "\n".join(text_chunks).strip()

    if not text:
        # Fallback: scanned PDF -> OCR (kept out of the hot path)
        text = _ocr_fallback(file_bytes)
    return text


def parse_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _ocr_fallback(file_bytes: bytes) -> str:
    # Placeholder: rasterize pages (pdf2image) + pytesseract.image_to_string.
    # Kept separate so it only runs when text extraction genuinely fails.
    return ""


def parse_resume(filename: str, file_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        return parse_pdf(file_bytes)
    if filename.lower().endswith(".docx"):
        return parse_docx(file_bytes)
    raise ValueError("Unsupported file type. Please upload a PDF or DOCX.")
