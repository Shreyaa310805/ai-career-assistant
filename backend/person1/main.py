from fastapi import FastAPI, UploadFile, File, HTTPException
from parser import extract_text_from_pdf, extract_text_from_docx

app = FastAPI(title="Person 1 - Resume & ATS Module")

@app.get("/health")
def health_check():
    return {"status": "ok", "module": "Resume & ATS"}

@app.post("/api/resume/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload a resume file (PDF or DOCX) and return extracted text."""
    filename = file.filename.lower()
    contents = await file.read()
    
    if filename.endswith(".pdf"):
        extracted_text = extract_text_from_pdf(contents)
    elif filename.endswith(".docx"):
        extracted_text = extract_text_from_docx(contents)
    else:
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file format. Please upload a PDF or DOCX file."
        )

    if not extracted_text:
        raise HTTPException(
            status_code=400, 
            detail="Could not extract text from the file. Ensure it is not an image-only PDF."
        )

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "extracted_text": extracted_text
    }
