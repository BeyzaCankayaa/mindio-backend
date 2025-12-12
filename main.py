from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ==================== LOAD ENV ====================
load_dotenv()

# ==================== ROUTER IMPORTS ====================
from auth import router as auth_router
from mood import router as mood_router
from chat import router as chat_router
from personality import router as personality_router
from suggestions import router as suggestions_router
from gamification import router as gamification_router
from stats import router as stats_router
from user_profile import router as user_router

# ==================== DATABASE INIT ====================
from database import engine
from models import Base

Base.metadata.create_all(bind=engine)

# ==================== APP CONFIG ====================
app = FastAPI(
    title="Mindio Backend",
    description="Mindio – FastAPI backend for mobile mental health assistant",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ==================== CORS SETTINGS ====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== ROUTERS ====================
app.include_router(auth_router)
app.include_router(mood_router)
app.include_router(chat_router)
app.include_router(personality_router)
app.include_router(suggestions_router)
app.include_router(gamification_router)
app.include_router(stats_router)
app.include_router(user_router)

# ==================== HEALTH CHECK ====================
@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "message": "Mindio backend is running"
    }
