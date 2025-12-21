# stats.py (FULL)
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from auth import get_current_user
from models import (
    User,
    Suggestion,
    SuggestionReaction,
    Gamification,
    ChatActivity,  # <-- activity.py eklediysek model adı bu olmalı
)

router = APIRouter(prefix="/stats", tags=["Stats"])


def _today_date_expr(db: Session, dt_col):
    """
    Postgres'ta timezone bug'ını azaltmak için created_at'i Europe/Istanbul gününe göre date'e çevirir.
    Diğer DB'lerde düz func.date kullanır.
    """
    try:
        dialect = db.bind.dialect.name  # type: ignore
    except Exception:
        dialect = ""

    if dialect == "postgresql":
        # created_at timestamptz ise: AT TIME ZONE ile TR gününe çevir
        # func.timezone('Europe/Istanbul', col) -> timestamp (no tz)
        return func.date(func.timezone("Europe/Istanbul", dt_col))
    return func.date(dt_col)


@router.get("/today")
def stats_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()

    # 1) total_chats (bugün)
    # ChatActivity modelinde day/date alanı yoksa created_at üzerinden sayıyoruz.
    chat_day = _today_date_expr(db, ChatActivity.created_at)
    total_chats = (
        db.query(ChatActivity)
        .filter(ChatActivity.user_id == current_user.id, chat_day == today)
        .count()
    )

    # 2) suggestions_created (bugün)  ✅ APPROVAL ŞARTI YOK
    sug_day = _today_date_expr(db, Suggestion.created_at)
    suggestions_created = (
        db.query(Suggestion)
        .filter(Suggestion.user_id == current_user.id, sug_day == today)
        .count()
    )

    # 3) likes_given (bugün) -> user’ın verdiği reaction sayısı
    react_day = _today_date_expr(db, SuggestionReaction.created_at)
    likes_given = (
        db.query(SuggestionReaction)
        .filter(SuggestionReaction.user_id == current_user.id, react_day == today)
        .count()
    )

    # 4) points (gamification)
    gam = db.query(Gamification).filter(Gamification.user_id == current_user.id).first()
    points = int(gam.points) if gam else 0

    return {
        "total_chats": int(total_chats),
        "suggestions_created": int(suggestions_created),
        "likes_given": int(likes_given),
        "points": int(points),
    }
# Alias for main.py imports (backward-compat)
stats_router = router
