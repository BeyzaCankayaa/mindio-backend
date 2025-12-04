# suggestions.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Suggestion

router = APIRouter(prefix="/suggestions", tags=["Crowdsourcing"])


class SuggestionCreate(BaseModel):
    user_id: int | None = None
    text: str


class SuggestionDTO(BaseModel):
    id: int
    user_id: int | None
    text: str

    class Config:
        orm_mode = True


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=SuggestionDTO)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db)   # ❗ Burada da Depends
):
   
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Suggestion text cannot be empty.")

    if len(text) > 500:
        raise HTTPException(status_code=400, detail="Suggestion is too long (max 500 chars).")

    suggestion = Suggestion(
        user_id=payload.user_id,
        text=text,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


@router.get("/", response_model=list[SuggestionDTO])
def list_suggestions(
    db: Session = Depends(get_db)   # ❗ Burada da
):
   
    suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.is_approved == True)
        .order_by(Suggestion.created_at.desc())
        .limit(50)
        .all()
    )
    return suggestions
