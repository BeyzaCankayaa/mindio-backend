# stats.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User, Suggestion, Gamification
from auth import get_current_user  # 🔑 Token'dan user çekmek için


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
    current_user: User = Depends(get_current_user),  # ✅ user_id query’den değil token’dan
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    # Kullanıcının gönderdiği suggestion sayısı
    total_suggestions = (
        db.query(Suggestion)
        .filter(
            Suggestion.user_id == user_id,
            Suggestion.is_approved == True,
        )
        .count()
    )

    # Şimdilik chat & like tablolarımız yok, 0 dönüyoruz
    total_chats = 0
    total_likes = 0

    # Gamification puanları
    gam = (
        db.query(Gamification)
        .filter(Gamification.user_id == user_id)
        .first()
    )

    points = gam.points if gam else 0
    badge_level = gam.badge_level if gam else "Newbie"

    return UserStatsResponse(
        user_id=user_id,
        total_suggestions=total_suggestions,
        total_chats=total_chats,
        total_likes=total_likes,
        points=points,
        badge_level=badge_level,
    )
