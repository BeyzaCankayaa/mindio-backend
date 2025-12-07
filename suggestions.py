# suggestions.py

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database import get_db
from models import Suggestion

router = APIRouter(prefix="/suggestions", tags=["Crowdsourcing"])


# ---------- SCHEMAS ----------

class SuggestionCreate(BaseModel):
    # user_id'i opsiyonel bırakalım, ister gönder ister göndermesin
    user_id: Optional[int] = None
    text: str


class SuggestionDTO(BaseModel):
    id: int
    user_id: Optional[int]
    text: str

    class Config:
        # Pydantic v2 (eskiden orm_mode = True)
        from_attributes = True


# ---------- ROUTES ----------

@router.post(
    "/",
    response_model=SuggestionDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
):
    """
    POST /suggestions

    Body örneği:
    {
      "user_id": 1,
      "text": "Bugün 10 dakika yürüyüş dene."
    }
    """

    text = payload.text.strip()

    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suggestion text cannot be empty.",
        )

    if len(text) > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suggestion is too long (max 500 chars).",
        )

    suggestion = Suggestion(
        user_id=payload.user_id,
        text=text,
    )

    try:
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    except SQLAlchemyError:
        db.rollback()
        # Lokalde hata görmen için biraz net mesaj veriyorum
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating suggestion.",
        )

    return suggestion


@router.get(
    "/{user_id}",
    response_model=List[SuggestionDTO],
)
def list_suggestions(
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    GET /suggestions/{user_id}
    Örn: /suggestions/1

    Response örneği:
    [
      {
        "id": 5,
        "user_id": 1,
        "text": "Bugün 10 dakika yürüyüş dene."
      }
    ]
    """

    suggestions = (
        db.query(Suggestion)
        .filter(
            Suggestion.user_id == user_id,
            Suggestion.is_approved == True,
        )
        .order_by(Suggestion.created_at.desc())
        .limit(50)
        .all()
    )

    return suggestions
