# stats.py (FULL REVISE - fixes NULL created_at + correct counting)

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text

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

    # ✅ IMPORTANT: Your DB has NULL created_at for suggestions.
    # We count "today" by Postgres CURRENT_DATE using:
    #   COALESCE(created_at::date, CURRENT_DATE) = CURRENT_DATE
    # So old rows with NULL created_at won't break progress.

    suggestions_created = (
        db.query(func.count(Suggestion.id))
        .filter(
            Suggestion.user_id == user_id,
            func.coalesce(func.date(Suggestion.created_at), func.current_date()) == func.current_date(),
        )
        .scalar()
        or 0
    )

    likes_given = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.user_id == user_id,
            SuggestionReaction.reaction == "like",
            func.coalesce(func.date(SuggestionReaction.created_at), func.current_date()) == func.current_date(),
        )
        .scalar()
        or 0
    )

    gam = db.query(Gamification).filter(Gamification.user_id == user_id).first()
    points = int(gam.points) if gam else 0

    # If chat activity increments points, keep this proxy
    total_chats = points

    return TodayStatsResponse(
        build="stats-fix-2025-12-21-03",
        total_chats=int(total_chats),
        suggestions_created=int(suggestions_created),
        likes_given=int(likes_given),
        points=int(points),
    )


# ✅ main.py import compatibility
stats_router = router
