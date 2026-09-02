from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import access, applications, auth, career
from app.core.config import get_settings
from app.api.routes.resumes import router as resumes_router
from app.db.resume_session import init_db as init_resume_db
from app.services.resumes.exceptions import ApiError
from app.services.resumes.response import error_payload

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The ATS module has its own, isolated persistence schema.
    await init_resume_db()
    yield


app = FastAPI(title="AI Career Assistant API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(access.router, prefix="/api/v1")
app.include_router(applications.router, prefix="/api/v1")
app.include_router(resumes_router, prefix="/api/v1")
app.include_router(career.router, prefix="/api/v1")


@app.exception_handler(ApiError)
async def handle_resume_api_error(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


@app.get("/health")
def health():
    return {"status": "ok"}
