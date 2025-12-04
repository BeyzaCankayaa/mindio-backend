# gamification.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Gamification

router = APIRouter(prefix="/gamification", tags=["Gamification"])


class PointsRequest(BaseModel):
    user_id: int
    points: int  # eklenecek puan


class GamificationDTO(BaseModel):
    user_id: int
    points: int
    badge_level: str

    class Config:
        orm_mode = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def calculate_badge(points: int) -> str:
    if points >= 200:
        return "Gold"
    elif points >= 100:
        return "Silver"
    elif points >= 50:
        return "Bronze"
    else:
        return "Newbie"


@router.post("/add-points", response_model=GamificationDTO)
def add_points(
    payload: PointsRequest,
    db: Session = Depends(get_db)    # ❗ Burada da Depends
):
    """
    Kullanıcıya puan ekler, badge seviyesini otomatik günceller.
    """
    if payload.points <= 0:
        raise HTTPException(status_code=400, detail="Points must be positive.")

    record = db.query(Gamification).filter(Gamification.user_id == payload.user_id).first()
    if not record:
        record = Gamification(user_id=payload.user_id, points=0, badge_level="Newbie")
        db.add(record)
        db.commit()
        db.refresh(record)

    record.points += payload.points
    record.badge_level = calculate_badge(record.points)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{user_id}", response_model=GamificationDTO)
def get_gamification(
    user_id: int,
    db: Session = Depends(get_db)    # ❗ Burada da
):
    """
    Kullanıcının puan ve badge bilgisini döner.
    """
    record = db.query(Gamification).filter(Gamification.user_id == user_id).first()
    if not record:
        record = Gamification(user_id=user_id, points=0, badge_level="Newbie")
        db.add(record)
        db.commit()
        db.refresh(record)
    return record
