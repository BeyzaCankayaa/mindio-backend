# suggestions.py
import os
from typing import List, Optional, Literal
from datetime import date

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc, case

from database import get_db
from models import (
    Suggestion,
    SuggestionReaction,
    SuggestionSave,
    SuggestionComment,      # ✅ FIX: comment endpoints için LAZIM
    User,
    PersonalityResponse,
    GlobalDailySuggestion,  # ✅ GLOBAL DAILY TABLE
)
from auth import get_current_user
from ai_client import generate_response, AIClientError

router = APIRouter(prefix="/suggestions", tags=["Crowdsourcing"])


# ===================== SCHEMAS =====================

class SuggestionCreate(BaseModel):
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


class DailyIngestRequest(BaseModel):
    text: str


# ===================== HELPERS =====================

def _validate_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    if len(t) > 500:
        raise HTTPException(status_code=400, detail="Text is too long (max 500 chars).")
    return t


def _likes_dislikes(db: Session, suggestion_id: int) -> tuple[int, int]:
    likes = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.suggestion_id == suggestion_id,
            SuggestionReaction.reaction == "like",
        )
        .scalar()
        or 0
    )
    dislikes = (
        db.query(func.count(SuggestionReaction.id))
        .filter(
            SuggestionReaction.suggestion_id == suggestion_id,
            SuggestionReaction.reaction == "dislike",
        )
        .scalar()
        or 0
    )
    return int(likes), int(dislikes)


def _is_saved(db: Session, suggestion_id: int, user_id: int) -> bool:
    return (
        db.query(SuggestionSave)
        .filter(
            SuggestionSave.suggestion_id == suggestion_id,
            SuggestionSave.user_id == user_id,
        )
        .first()
        is not None
    )


def _build_user_context(db: Session, user_id: int) -> str:
    p = (
        db.query(PersonalityResponse)
        .filter(PersonalityResponse.user_id == user_id)
        .order_by(desc(PersonalityResponse.id))
        .first()
    )

    instruction = (
        "INSTRUCTION:\n"
        "- Speak Turkish.\n"
        "- Produce ONE short daily suggestion (1-2 sentences max).\n"
        "- Actionable, kind, practical.\n"
        "- No medical diagnosis.\n"
    )

    if not p:
        return (
            "USER PROFILE:\n"
            "- AgeRange: Unknown\n"
            "- Gender: Unknown\n"
            "- CurrentMood: Unknown\n"
            "- SupportTopics: General wellbeing\n\n"
            + instruction
        )

    topics = (p.q4_answer or "").strip() or "General wellbeing"

    return (
        "USER PROFILE:\n"
        f"- AgeRange: {p.q1_answer}\n"
        f"- Gender: {p.q2_answer}\n"
        f"- CurrentMood: {p.q3_answer}\n"
        f"- SupportTopics: {topics}\n\n"
        + instruction
    )


def _build_user_data(db: Session, user_id: int) -> dict:
    p = (
        db.query(PersonalityResponse)
        .filter(PersonalityResponse.user_id == user_id)
        .order_by(desc(PersonalityResponse.id))
        .first()
    )

    if not p:
        return {
            "age": "unknown",
            "gender": "unknown",
            "mood": "unknown",
            "supportTopics": "General wellbeing",
            "location": "unknown",
        }

    topics = (p.q4_answer or "").strip() or "General wellbeing"

    return {
        "age": p.q1_answer or "unknown",
        "gender": p.q2_answer or "unknown",
        "mood": p.q3_answer or "unknown",
        "supportTopics": topics,
        "location": "unknown",
    }


async def _generate_ai_suggestion_text(db: Session, user_id: int) -> str:
    user_data = _build_user_data(db, user_id)
    prompt = (
        "Kullanıcının profil bilgilerine göre bugün için TEK bir öneri üret. "
        "Kısa olsun (1-2 cümle)."
    )

    try:
        reply = await generate_response(
            message=prompt,
            history=[],
            user_id=user_id,
            user_data=user_data,
            user_context=_build_user_context(db, user_id),
        )
    except AIClientError as e:
        raise HTTPException(status_code=502, detail=f"AIClientError: {str(e)}")

    return _validate_text(reply)


def _get_fallback_global_tip(db: Session) -> Suggestion:
    total = (
        db.query(func.count(Suggestion.id))
        .filter(Suggestion.is_approved.is_(True))
        .scalar()
        or 0
    )
    if total == 0:
        raise HTTPException(status_code=404, detail="No suggestions available.")

    idx = date.today().toordinal() % total
    tip = (
        db.query(Suggestion)
        .filter(Suggestion.is_approved.is_(True))
        .order_by(Suggestion.id.asc())
        .offset(idx)
        .limit(1)
        .first()
    )

    if not tip:
        tip = (
            db.query(Suggestion)
            .filter(Suggestion.is_approved.is_(True))
            .order_by(Suggestion.id.asc())
            .first()
        )

    if not tip:
        raise HTTPException(status_code=404, detail="No suggestions available.")

    return tip


# ===================== ROUTES =====================

@router.post("/ingest-daily", status_code=200)
def ingest_daily_suggestion(
    payload: DailyIngestRequest,
    db: Session = Depends(get_db),
    x_api_key: str = Header(default="", alias="X-API-KEY"),
):
    expected = (os.getenv("DAILY_INGEST_KEY") or "").strip()
    if not expected:
        raise HTTPException(status_code=500, detail="DAILY_INGEST_KEY is not configured on server.")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid API key")

    text = _validate_text(payload.text)
    today = date.today()

    suggestion = Suggestion(user_id=None, text=text, is_approved=True)
    try:
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while saving daily suggestion.")

    try:
        row = db.query(GlobalDailySuggestion).filter(GlobalDailySuggestion.day == today).first()
        if row:
            row.suggestion_id = suggestion.id
        else:
            db.add(GlobalDailySuggestion(day=today, suggestion_id=suggestion.id))
        db.commit()
    except SQLAlchemyError:
        db.rollback()

    return {"status": "ok", "day": str(today), "suggestion_id": suggestion.id}


@router.get("/daily", response_model=SuggestionDailyDTO)
def get_daily_suggestion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()

    row = db.query(GlobalDailySuggestion).filter(GlobalDailySuggestion.day == today).first()
    tip: Optional[Suggestion] = None

    if row:
        tip = db.query(Suggestion).filter(Suggestion.id == row.suggestion_id).first()

    if not tip:
        tip = _get_fallback_global_tip(db)

    likes, dislikes = _likes_dislikes(db, tip.id)
    saved = _is_saved(db, tip.id, current_user.id)

    return {
        "id": tip.id,
        "user_id": tip.user_id,
        "text": tip.text,
        "likes": likes,
        "dislikes": dislikes,
        "is_saved": saved,
    }


@router.post("/", response_model=SuggestionDTO, status_code=201)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    text = _validate_text(payload.text)
    suggestion = Suggestion(user_id=current_user.id, text=text)

    try:
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while creating suggestion.")

    return suggestion


@router.post("/generate", response_model=SuggestionDTO, status_code=201)
async def generate_daily_ai_suggestion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        text = await _generate_ai_suggestion_text(db, current_user.id)

        suggestion = Suggestion(user_id=current_user.id, text=text, is_approved=True)
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
        return suggestion

    except (HTTPException, SQLAlchemyError):  # ✅ FIX: AI 502 dahil her şeyde fallback
        try:
            db.rollback()
        except Exception:
            pass
        return _get_fallback_global_tip(db)


@router.get("/saved/me", response_model=List[SuggestionDTO])
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
    ordering = case({sid: i for i, sid in enumerate(suggestion_ids)}, value=Suggestion.id)

    return (
        db.query(Suggestion)
        .filter(Suggestion.id.in_(suggestion_ids))
        .order_by(ordering)
        .all()
    )


@router.post("/react", status_code=200)
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

    return {"status": "ok"}


@router.post("/save", status_code=200)
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
            db.add(SuggestionSave(suggestion_id=payload.suggestion_id, user_id=current_user.id))
            db.commit()
            return {"status": "ok", "saved": True}
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while toggling save.")


@router.post("/comment", response_model=CommentDTO, status_code=201)
def add_comment(
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    suggestion = db.query(Suggestion).filter(Suggestion.id == payload.suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found.")

    text = _validate_text(payload.text)
    comment = SuggestionComment(suggestion_id=payload.suggestion_id, user_id=current_user.id, text=text)

    try:
        db.add(comment)
        db.commit()
        db.refresh(comment)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while creating comment.")

    return comment


@router.get("/comment/{suggestion_id}", response_model=List[CommentDTO])
def list_comments(suggestion_id: int, db: Session = Depends(get_db)):
    return (
        db.query(SuggestionComment)
        .filter(SuggestionComment.suggestion_id == suggestion_id)
        .order_by(desc(SuggestionComment.created_at))
        .limit(100)
        .all()
    )


@router.get("/{user_id}", response_model=List[SuggestionDTO])
def list_user_suggestions(user_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Suggestion)
        .filter(Suggestion.user_id == user_id, Suggestion.is_approved.is_(True))
        .order_by(desc(Suggestion.created_at))
        .limit(50)
        .all()
    )
