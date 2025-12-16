from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import User  # User kesin var
from auth import get_current_user

from ai_client import generate_response, AIClientError

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Any]] = None

    # ✅ TRANSITION MODE:
    # Flutter şu an gönderiyor olabilir. Biz KULLANMAYACAĞIZ (n8n'e yollamıyoruz),
    # sadece DB boşsa userContext fallback üretmek için kullanacağız.
    userData: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str


def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    return history if isinstance(history, list) else []


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def build_user_context_from_profile_dict(profile: Dict[str, Any]) -> str:
    """
    profile dict içinden userContext string üretir.
    Farklı key isimlerini toleranslı okur (age/age_range, supportTopics/support_topics vs.)
    """
    age = _safe_str(profile.get("age_range") or profile.get("age") or profile.get("ageRange") or "unknown")
    gender = _safe_str(profile.get("gender") or "unknown")
    mood = _safe_str(profile.get("mood") or profile.get("current_mood") or profile.get("mood_default") or "neutral")
    topics = _safe_str(profile.get("support_topics") or profile.get("supportTopics") or profile.get("topics") or "general")
    location = _safe_str(profile.get("location") or "unknown")

    # n8n string bekliyor
    return f"Age: {age}, Gender: {gender}, Mood: {mood}, Topics: {topics}, Location: {location}"


def _instruction_block() -> str:
    # Bu blok LLM davranışı için güzel; userContext string'ine ekliyoruz.
    # (n8n tarafında prompt'a gömüyorsan bu kısmı oraya taşıyabilirsin.)
    return (
        " | INSTRUCTION: Speak Turkish. Short, clear, step-by-step. "
        "Be supportive and practical. Avoid medical diagnosis. "
        "If symptoms are severe or persistent, suggest seeking a professional."
    )


def fetch_user_profile_context(db: Session, user_id: int, fallback_userData: Optional[Dict[str, Any]]) -> str:
    """
    1) Öncelik: DB'de user_profile varsa ondan üret
    2) Yoksa: PersonalityResponse (eski yapı) varsa ondan üret (backward compat)
    3) Yoksa: fallback_userData ile üret
    4) O da yoksa: unknown
    """
    # --- 1) Try UserProfile model (if exists) ---
    try:
        from models import UserProfile  # type: ignore
        profile_obj = (
            db.query(UserProfile)
            .filter(UserProfile.user_id == user_id)
            .order_by(desc(UserProfile.id))
            .first()
        )
        if profile_obj:
            # obj -> dict (toleranslı)
            profile_dict = {
                "age_range": getattr(profile_obj, "age_range", None) or getattr(profile_obj, "age", None),
                "gender": getattr(profile_obj, "gender", None),
                "mood": getattr(profile_obj, "mood", None) or getattr(profile_obj, "current_mood", None),
                "support_topics": getattr(profile_obj, "support_topics", None) or getattr(profile_obj, "supportTopics", None),
                "location": getattr(profile_obj, "location", None),
            }
            return build_user_context_from_profile_dict(profile_dict) + _instruction_block()
    except Exception:
        # UserProfile yoksa veya import patlarsa sorun etmiyoruz (repo henüz migrate olmamış olabilir)
        pass

    # --- 2) Backward compat: PersonalityResponse ---
    try:
        from models import PersonalityResponse  # type: ignore

        personality = (
            db.query(PersonalityResponse)
            .filter(PersonalityResponse.user_id == user_id)
            .order_by(desc(PersonalityResponse.id))
            .first()
        )
        if personality:
            topics = (_safe_str(getattr(personality, "q4_answer", "")) or "general wellbeing")
            profile_dict = {
                "age_range": getattr(personality, "q1_answer", None) or "unknown",
                "gender": getattr(personality, "q2_answer", None) or "unknown",
                "mood": getattr(personality, "q3_answer", None) or "neutral",
                "support_topics": topics,
                "location": "unknown",
            }
            return build_user_context_from_profile_dict(profile_dict) + _instruction_block()
    except Exception:
        pass

    # --- 3) Fallback: userData from Flutter (temporary) ---
    if isinstance(fallback_userData, dict) and fallback_userData:
        return build_user_context_from_profile_dict(fallback_userData) + _instruction_block()

    # --- 4) Default unknown ---
    return build_user_context_from_profile_dict({}) + _instruction_block()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")

    history = _normalize_history(payload.history)

    # ✅ NEW: userContext DB’den (öncelikli) okunur, userData sadece fallback
    user_context = fetch_user_profile_context(db=db, user_id=current_user.id, fallback_userData=payload.userData)

    try:
        # ✅ n8n'e: message + history + userContext (string)
        reply = await generate_response(message=msg, history=history, user_context=user_context)
        return ChatResponse(reply=reply)

    except AIClientError as e:
        print("AIClientError:", str(e))
        return ChatResponse(reply="Şu an cevap üretemedim. Bir daha dener misin?")

    except Exception as e:
        print("Unexpected error in /ai/chat:", str(e))
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {str(e)}")
