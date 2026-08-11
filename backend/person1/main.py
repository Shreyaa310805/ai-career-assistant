from fastapi import FastAPI

app = FastAPI(title="Person 1 - Resume & ATS Module")

@app.get("/health")
def health_check():
    return {"status": "ok", "module": "Resume & ATS"}
