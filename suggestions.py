# suggestions.py

from typing import List, Optional, Literal
from datetime import date

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc, case

from database import get_db
from models import (
    Suggestion,
    SuggestionReaction,
    SuggestionSave,
    SuggestionComment,
    User,
    PersonalityResponse,
    UserDailySuggestion,
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
    """
    AI'ye verilecek context: personality varsa kullan, yoksa fallback.
    """
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


async def _generate_ai_suggestion_and_save(db: Session, current_user: User) -> Suggestion:
    """
    AI -> text üret -> suggestions tablosuna kaydet -> Suggestion döndür.
    """
    user_context = _build_user_context(db, current_user.id)

    # AI'ye net görev:
    prompt = (
        "Kullanıcının profil bilgilerine göre bugün için TEK bir öneri üret. "
        "Kısa olsun (1-2 cümle)."
    )

    # ✅ KANIT LOG (AI'ye giden payload)
    print("🚀 AI REQUEST PAYLOAD:")
    print({"message": prompt, "history": [], "userContext": user_context})

    try:
        reply = await generate_response(
            message=prompt,
            history=[],
            user_context=user_context,
        )
    except AIClientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AIClientError: {str(e)}",
        )

    text = _validate_text(reply)

    suggestion = Suggestion(
        user_id=current_user.id,
        text=text,
        is_approved=True,  # AI üretileni daily’de göstereceğiz
    )

    try:
        db.add(suggestion)
        db.commit()
        db.refresh(suggestion)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error while saving AI suggestion.")

    return suggestion


def _get_global_daily_tip(db: Session) -> Suggestion:
    """
    Eski davranış: global deterministic daily tip.
    (AI fail olursa fallback olarak da kullanıyoruz)
    """
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

@router.post(
    "/",
    response_model=SuggestionDTO,
    status_code=status.HTTP_201_CREATED,
)
def create_suggestion(
    payload: SuggestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crowdsourcing öneri ekleme:
    - Token zorunlu
    - user_id otomatik current_user.id
    """
    text = _validate_text(payload.text)

    suggestion = Suggestion(
        user_id=current_user.id,
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


@router.post(
    "/generate",
    response_model=SuggestionDTO,
    status_code=status.HTTP_201_CREATED,
)
async def generate_daily_ai_suggestion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Kullanıcıya özel AI önerisi üretir ve DB'ye kaydeder.
    Not: daily endpointi zaten gerekirse bunu çağırıyor.
    """
    suggestion = await _generate_ai_suggestion_and_save(db, current_user)
    return suggestion


@router.get(
    "/daily",
    response_model=SuggestionDailyDTO,
)
async def get_daily_suggestion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ✅ Yeni davranış:
    1) Bugün için bu kullanıcıya özel daily mapping var mı bak
    2) Varsa onu döndür
    3) Yoksa AI ile üret -> suggestions'a kaydet -> user_daily_suggestions'a (user, day) mapping ekle -> döndür
    4) AI patlarsa fallback: global deterministic tip döndür (eski davranış)
    """

    today = date.today()

    mapping = (
        db.query(UserDailySuggestion)
        .filter(
            UserDailySuggestion.user_id == current_user.id,
            UserDailySuggestion.day == today,
        )
        .first()
    )

    tip: Optional[Suggestion] = None

    if mapping:
        tip = db.query(Suggestion).filter(Suggestion.id == mapping.suggestion_id).first()

    if not tip:
        # mapping yoksa: AI üretmeyi dene
        try:
            tip = await _generate_ai_suggestion_and_save(db, current_user)

            # mapping ekle
            try:
                db.add(
                    UserDailySuggestion(
                        user_id=current_user.id,
                        suggestion_id=tip.id,
                        day=today,
                    )
                )
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                # mapping eklenemese bile tip kaydı var, devam edelim
        except HTTPException:
            # AI fail -> fallback
            tip = _get_global_daily_tip(db)

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

    ordering = case(
        {sid: i for i, sid in enumerate(suggestion_ids)},
        value=Suggestion.id,
    )

    suggestions = (
        db.query(Suggestion)
        .filter(Suggestion.id.in_(suggestion_ids))
        .order_by(ordering)
        .all()
    )
    return suggestions


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
            Suggestion.is_approved.is_(True),
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
