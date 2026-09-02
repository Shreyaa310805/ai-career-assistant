import pytest

from app.exceptions import ExtractionError, UnsupportedFileTypeError
from app.services.extraction import (
    extract_jd_text,
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf,
)


def test_extract_text_from_pdf(sample_resume_pdf_bytes):
    text = extract_text_from_pdf(sample_resume_pdf_bytes)
    assert "Jane Doe" in text
    assert "jane.doe@example.com" in text


def test_extract_text_from_docx(sample_resume_docx_bytes):
    text = extract_text_from_docx(sample_resume_docx_bytes)
    assert "Jane Doe" in text
    assert "FastAPI" in text


def test_extract_text_dispatches_by_extension(sample_resume_docx_bytes):
    text = extract_text(sample_resume_docx_bytes, "resume.docx", None)
    assert "Jane Doe" in text


def test_extract_text_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(b"not a real file", "resume.txt", None)


def test_extract_text_rejects_corrupt_pdf():
    with pytest.raises(ExtractionError):
        extract_text(b"%PDF-1.4 not really a pdf", "resume.pdf", None)


def test_extract_jd_text_normalizes():
    text = extract_jd_text("  Some JD text\r\nwith \t  extra   spacing \n\n\n\nhere  ")
    assert text.startswith("Some JD text")
    assert "\n\n\n" not in text


def test_extract_jd_text_rejects_empty():
    with pytest.raises(ExtractionError):
        extract_jd_text("   ")
