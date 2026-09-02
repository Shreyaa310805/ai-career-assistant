"""
FastAPI application entrypoint for Module 1 (Resume & ATS).

Run standalone:
    uvicorn app.main:app --reload --port 8001

No Postgres, no Gemini key, and no other team's module required — see
.env.example / README.md.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.resumes import router as resumes_router
from app.config import get_settings
from app.database import init_db
from app.exceptions import ApiError
from app.response import error_payload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if not settings.gemini_enabled:
        logger.info(
            "GEMINI_API_KEY not set — running with the heuristic resume/JD "
            "parser. Set GEMINI_API_KEY in .env to use Gemini instead."
        )
    yield


app = FastAPI(
    title="Resume & ATS Module (Person 1)",
    description="Standalone backend for resume upload/parsing, ATS scoring, "
                 "JD matching, explainable screening, and resume versioning.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resumes_router, prefix=settings.api_v1_prefix)


@app.get("/health")
async def health():
    return {
        "success": True,
        "data": {"status": "ok", "gemini_enabled": settings.gemini_enabled},
        "error": None,
    }


# --------------------------------------------------------------------------
# Global exception handlers — normalize every error path to the standard
# {"success": false, "data": null, "error": {...}} contract (ISSUE-04).
# --------------------------------------------------------------------------
@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=422,
        content=error_payload(
            "VALIDATION_ERROR", "Request validation failed.", exc.errors()
        ),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    from fastapi.responses import JSONResponse

    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content=error_payload("INTERNAL_ERROR", "An unexpected error occurred."),
    )
