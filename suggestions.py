from typing import List, Optional, Literal

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc

from database import get_db
from models import (
    Suggestion,
    SuggestionReaction,
    SuggestionSave,
    SuggestionComment,
    User,
)
from auth import get_current_user

router = APIRouter(prefix="/suggestions", tags=["Crowdsourcing"])


# ===================== SCHEMAS =====================

class SuggestionCreate(BaseModel):
    user_id: Optional[int] = None
    text: str


class SuggestionDTO(BaseModel):
    id: int
    user_id: Optional[int]
    text: str

    class Config:
        from_attributes = True


class ReactionUpsert(BaseModel):
    suggestion_id: int
    reaction: Literal["like", "dislike"]


class SaveToggle(BaseModel):
    suggestion_id: int


class CommentCreate(BaseModel):
    suggestion_id: int
    text: str


class CommentDTO(BaseModel):
    id: int
    suggestion_id: int
    user_id: int
    text: str

    class Config:
        from_attributes = True


class SuggestionDailyDTO(BaseModel):
    id: int
    user_id: Optional[int]
    text: str
    likes: int
    dislikes: int
    is_saved: bool

    class Config:
        from_attributes = True


# ===================== HELPERS =====================

def _validate_text(text: str) -> str:
    t = text.strip()
    if not t:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    if len(t) > 500:
        raise HTTPException(status_code=400, detail="Text is too long (max 500 chars).")
    return t


# ===================== ROUTES =====================

@router.post(
    "/",
    response_model=SuggestionDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
):
    text = _validate_text(payload.text)

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
        raise HTTPException(status_code=500, detail="Database error while creating suggestion.")

    return suggestion


@router.get(
    "/daily",
    response_model=SuggestionDailyDTO,
)
def get_daily_suggestion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tip = (
        db.query(Suggestion)
        .filter(Suggestion.is_approved == True)
        .order_by(func.random())
        .first()
    )
    if not tip:
        raise HTTPException(status_code=404, detail="No suggestions available.")

    likes = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.suggestion_id == tip.id,
            SuggestionReaction.reaction == "like",
        )
        .scalar()
        or 0
    )
    dislikes = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.suggestion_id == tip.id,
            SuggestionReaction.reaction == "dislike",
        )
        .scalar()
        or 0
    )

    saved = (
        db.query(SuggestionSave)
        .filter(
            SuggestionSave.suggestion_id == tip.id,
            SuggestionSave.user_id == current_user.id,
        )
        .first()
        is not None
    )

    return {
        "id": tip.id,
        "user_id": tip.user_id,
        "text": tip.text,
        "likes": int(likes),
        "dislikes": int(dislikes),
        "is_saved": bool(saved),
    }


@router.get(
    "/{user_id}",
    response_model=List[SuggestionDTO],
)
def list_user_suggestions(
    user_id: int,
    db: Session = Depends(get_db),
):
    suggestions = (
        db.query(Suggestion)
        .filter(
            Suggestion.user_id == user_id,
            Suggestion.is_approved == True,
        )
        .order_by(desc(Suggestion.created_at))
        .limit(50)
        .all()
    )
    return suggestions


@router.post(
    "/react",
    status_code=status.HTTP_200_OK,
)
def react_to_suggestion(
    payload: ReactionUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = db.query(Suggestion).filter(Suggestion.id == payload.suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    existing = (
        db.query(SuggestionReaction)
        .filter(
            SuggestionReaction.suggestion_id == payload.suggestion_id,
            SuggestionReaction.user_id == current_user.id,
        )
        .first()
    )

    try:
        if existing:
            existing.reaction = payload.reaction
        else:
            db.add(
                SuggestionReaction(
                    suggestion_id=payload.suggestion_id,
                    user_id=current_user.id,
                    reaction=payload.reaction,
                )
            )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while saving reaction.")

    return {"status": "ok", "message": "Reaction saved."}


@router.post(
    "/save",
    status_code=status.HTTP_200_OK,
)
def toggle_save_suggestion(
    payload: SaveToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = db.query(Suggestion).filter(Suggestion.id == payload.suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    existing = (
        db.query(SuggestionSave)
        .filter(
            SuggestionSave.suggestion_id == payload.suggestion_id,
            SuggestionSave.user_id == current_user.id,
        )
        .first()
    )

    try:
        if existing:
            db.delete(existing)
            db.commit()
            return {"status": "ok", "saved": False}
        else:
            db.add(
                SuggestionSave(
                    suggestion_id=payload.suggestion_id,
                    user_id=current_user.id,
                )
            )
            db.commit()
            return {"status": "ok", "saved": True}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while toggling save.")


@router.post(
    "/comment",
    response_model=CommentDTO,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = db.query(Suggestion).filter(Suggestion.id == payload.suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    text = _validate_text(payload.text)

    comment = SuggestionComment(
        suggestion_id=payload.suggestion_id,
        user_id=current_user.id,
        text=text,
    )

    try:
        db.add(comment)
        db.commit()
        db.refresh(comment)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while creating comment.")

    return comment


@router.get(
    "/comment/{suggestion_id}",
    response_model=List[CommentDTO],
)
def list_comments(
    suggestion_id: int,
    db: Session = Depends(get_db),
):
    comments = (
        db.query(SuggestionComment)
        .filter(SuggestionComment.suggestion_id == suggestion_id)
        .order_by(desc(SuggestionComment.created_at))
        .limit(100)
        .all()
    )
    return comments


@router.get(
    "/saved/me",
    response_model=List[SuggestionDTO],
)
def list_my_saved(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved_rows = (
        db.query(SuggestionSave)
        .filter(SuggestionSave.user_id == current_user.id)
        .order_by(desc(SuggestionSave.created_at))
        .limit(100)
        .all()
    )
    if not saved_rows:
        return []

    suggestion_ids = [r.suggestion_id for r in saved_rows]

    suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.id.in_(suggestion_ids))
        .all()
    )

    by_id = {s.id: s for s in suggestions}
    ordered = [by_id[sid] for sid in suggestion_ids if sid in by_id]

    return ordered
