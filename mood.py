from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Mood, User
from auth import get_current_user

router = APIRouter(prefix="/mood", tags=["Mood"])


class MoodCreate(BaseModel):
    mood: str
    note: str | None = None


class MoodOut(BaseModel):
    id: int
    mood: str
    note: str | None
    created_at: datetime

    class Config:
        orm_mode = True


@router.post("/add", response_model=MoodOut)
def add_mood(
    payload: MoodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mood_entry = Mood(
        user_id=current_user.id,
        mood=payload.mood,
        note=payload.note,
    )
    db.add(mood_entry)
    db.commit()
    db.refresh(mood_entry)
    return mood_entry


@router.get("/list", response_model=list[MoodOut])
def list_moods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    moods = (
        db.query(Mood)
        .filter(Mood.user_id == current_user.id)
        .order_by(Mood.created_at.desc())
        .all()
    )
    return moods


@router.get("/today", response_model=MoodOut)
def today_mood(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = datetime.utcnow().date()

    mood_entry = (
        db.query(Mood)
        .filter(
            Mood.user_id == current_user.id,
            func.date(Mood.created_at) == today,
        )
        .order_by(Mood.created_at.desc())
        .first()
    )

    if not mood_entry:
        raise HTTPException(status_code=404, detail="No mood entry for today.")

    return mood_entry
