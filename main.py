from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from database import Base, engine
from auth import router as auth_router
from mood import router as mood_router
from chat import router as chat_router
from personality import router as personality_router
from suggestions import router as suggestions_router
from gamification import router as gamification_router
from stats import router as stats_router
from user_profile import router as user_router
from character import router as characters_router
from user_character import router as user_characters_router

app = FastAPI(
    title="Mindio Backend",
    description="Mindio – FastAPI backend",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(mood_router)
app.include_router(chat_router)
app.include_router(personality_router)
app.include_router(suggestions_router)
app.include_router(gamification_router)
app.include_router(stats_router)
app.include_router(user_router)
app.include_router(characters_router)
app.include_router(user_characters_router)

@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "Mindio backend is running"}
