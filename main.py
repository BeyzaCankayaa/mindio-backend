# main.py (FULL REVİZE)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ==================== LOAD ENV ====================
load_dotenv()

# ==================== DATABASE INIT ====================
from database import engine, SessionLocal
from models import Base



# ==================== SEED ====================
# from seed_characters import seed_characters_if_empty

# ==================== ROUTER IMPORTS ====================
from auth import router as auth_router
from mood import router as mood_router
from chat import router as chat_router
from personality import router as personality_router
from suggestions import router as suggestions_router
from gamification import router as gamification_router
from stats import router as stats_router
from stats import stats_router as stats_today_router  # ✅ NEW: /stats/today
from user_profile import router as user_router
from character import router as characters_router
from user_character import router as user_characters_router
from activity import router as activity_router  # ✅ NEW: /activity/chat

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

# ==================== STARTUP (SEED) ====================
# (seed varsa burada çağırıyordun, dokunmadım)

# ==================== ROUTERS ====================
app.include_router(auth_router)
app.include_router(mood_router)
app.include_router(chat_router)
app.include_router(personality_router)
app.include_router(suggestions_router)
app.include_router(gamification_router)

app.include_router(stats_router)         # /user/stats (mevcut)
app.include_router(stats_today_router)   # /stats/today (NEW)

app.include_router(activity_router)      # /activity/chat (NEW)

app.include_router(user_router)
app.include_router(characters_router)
app.include_router(user_characters_router)

# ==================== HEALTH CHECK ====================
@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Mindio backend is running"}
