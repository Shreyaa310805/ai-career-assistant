from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.skill_gap import router as skill_gap_router
from app.routers.priority import router as priority_router
from app.routers.what_if import router as what_if_router
from app.routers.recommendations import router as recommendations_router
from app.routers.roadmap import router as roadmap_router


app = FastAPI(
    title="Career Intelligence API",
    description="Person 3 - What-if & Career Intelligence Module",
    version="1.0.0"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(skill_gap_router)
app.include_router(priority_router)
app.include_router(what_if_router)
app.include_router(recommendations_router)
app.include_router(roadmap_router)


@app.get("/")
def home():
    return {
        "message": "Career Intelligence API is running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }
