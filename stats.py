# stats.py (FULL)
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from auth import get_current_user
from models import User, Suggestion, SuggestionReaction, Gamification

router = APIRouter(prefix="/stats", tags=["Stats"])


class TodayStatsResponse(BaseModel):
    build: str
    total_chats: int
    suggestions_created: int
    likes_given: int
    points: int


@router.get("/today", response_model=TodayStatsResponse)
def get_today_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    # ✅ DB "today" reference (timezone-safe)
    suggestions_created = (
        db.query(func.count(Suggestion.id))
        .filter(
            Suggestion.user_id == user_id,
            func.date(Suggestion.created_at) == func.current_date(),
        )
        .scalar()
        or 0
    )

    likes_given = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.user_id == user_id,
            SuggestionReaction.reaction == "like",
            func.date(SuggestionReaction.created_at) == func.current_date(),
        )
        .scalar()
        or 0
    )

    # points (chat activity increments this in your backend)
    gam = db.query(Gamification).filter(Gamification.user_id == user_id).first()
    points = int(gam.points) if gam else 0

    # If you don't have a separate chat counter table yet, use points as total_chats proxy
    total_chats = points

    return TodayStatsResponse(
        build="stats-fix-2025-12-21-02",
        total_chats=int(total_chats),
        suggestions_created=int(suggestions_created),
        likes_given=int(likes_given),
        points=int(points),
    )


# ✅ main.py import compatibility
stats_router = router
