import pymupdf  # PyMuPDF
import docx
from io import BytesIO

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts raw text from PDF file bytes using PyMuPDF."""
    text = ""
    with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text.strip()

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts raw text from DOCX file bytes using python-docx."""
    doc = docx.Document(BytesIO(file_bytes))
    full_text = [paragraph.text for paragraph in doc.paragraphs if paragraph.text]
    return "\n".join(full_text).strip()
