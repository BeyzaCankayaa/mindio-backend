# stats.py (FULL REVİZE)

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import User, Suggestion, Gamification, SuggestionReaction, ChatActivity
from auth import get_current_user


# =========================
# Existing: /user/stats (keep)
# =========================
router = APIRouter(prefix="/user", tags=["User Stats"])


class UserStatsResponse(BaseModel):
    user_id: int
    total_suggestions: int
    total_chats: int
    total_likes: int
    points: int
    badge_level: str


@router.get("/stats", response_model=UserStatsResponse)
def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    total_suggestions = (
        db.query(func.count(Suggestion.id))
        .filter(
            Suggestion.user_id == user_id,
            Suggestion.is_approved.is_(True),
        )
        .scalar()
        or 0
    )

    total_chats = (
        db.query(func.count(ChatActivity.id))
        .filter(ChatActivity.user_id == user_id)
        .scalar()
        or 0
    )

    total_likes = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.user_id == user_id,
            SuggestionReaction.reaction == "like",
        )
        .scalar()
        or 0
    )

    gam = db.query(Gamification).filter(Gamification.user_id == user_id).first()
    points = int(gam.points) if gam else 0
    badge_level = gam.badge_level if gam else "Newbie"

    return UserStatsResponse(
        user_id=user_id,
        total_suggestions=int(total_suggestions),
        total_chats=int(total_chats),
        total_likes=int(total_likes),
        points=points,
        badge_level=badge_level,
    )


# =========================
# New: /stats/today (homepage)
# =========================
stats_router = APIRouter(prefix="/stats", tags=["Stats"])


@stats_router.get("/today")
def stats_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id
    today = date.today()

    total_chats = (
        db.query(func.count(ChatActivity.id))
        .filter(
            ChatActivity.user_id == user_id,
            func.date(ChatActivity.created_at) == today,
        )
        .scalar()
        or 0
    )

    suggestions_created = (
        db.query(func.count(Suggestion.id))
        .filter(
            Suggestion.user_id == user_id,
            func.date(Suggestion.created_at) == today,
        )
        .scalar()
        or 0
    )

    likes_given = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.user_id == user_id,
            SuggestionReaction.reaction == "like",
            func.date(SuggestionReaction.created_at) == today,
        )
        .scalar()
        or 0
    )

    gam = db.query(Gamification).filter(Gamification.user_id == user_id).first()
    points = int(gam.points) if gam else 0

    return {
        "total_chats": int(total_chats),
        "suggestions_created": int(suggestions_created),
        "likes_given": int(likes_given),
        "points": int(points),
    }
