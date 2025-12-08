# stats.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Suggestion, Gamification

router = APIRouter(prefix="/user", tags=["User Stats"])


class UserStats(BaseModel):
    user_id: int
    total_suggestions: int
    total_chats: int
    total_likes: int
    points: int
    badge_level: str


@router.get("/stats", response_model=UserStats)
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """
    Kullanıcının genel istatistiklerini döner.

    Şu an için:
    - total_suggestions: suggestions tablosundan count
    - total_chats: (chat tablosu henüz yok) -> 0
    - total_likes: (likes tablosu henüz yok) -> 0
    - points, badge_level: gamification tablosundan
    """

    # Kullanıcının kaç tane suggestion gönderdiği
    total_suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.user_id == user_id)
        .count()
    )

    # Gamification kaydı varsa al
    gam = (
        db.query(Gamification)
        .filter(Gamification.user_id == user_id)
        .first()
    )

    # TODO: Chat ve Like tabloları eklendiğinde burayı güncelle
    total_chats = 0
    total_likes = 0

    return UserStats(
        user_id=user_id,
        total_suggestions=total_suggestions,
        total_chats=total_chats,
        total_likes=total_likes,
        points=gam.points if gam else 0,
        badge_level=gam.badge_level if gam else "Newbie",
    )
