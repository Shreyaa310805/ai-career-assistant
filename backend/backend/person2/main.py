from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from database import Base, engine
from routers import interviews

# Creates the interviews table if it doesn't exist yet.
# Fine for this MVP; a real migration tool (Alembic) can replace this later — see PART 6.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Person 2 - AI Interview Module")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # MVP only — tighten this once the real frontend origin is known
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            },
        },
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "module": "AI Interview"}


app.include_router(interviews.router)