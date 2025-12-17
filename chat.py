from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import User
from auth import get_current_user

from ai_client import generate_response, AIClientError

router = APIRouter(prefix="/ai", tags=["AI"])


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Any]] = None

    # ✅ TRANSITION MODE (Flutter şu an gönderebilir)
    # DB boşsa fallback olarak kullanacağız
    userData: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str


def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    return history if isinstance(history, list) else []


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _instruction_block() -> str:
    return (
        "INSTRUCTION:\n"
        "- Speak Turkish.\n"
        "- Short, clear, practical.\n"
        "- If user is 45+ and gender is male use 'Bey', if female use 'Hanım'.\n"
        "- Avoid medical diagnosis.\n"
    )


def build_user_context(profile: Dict[str, Any]) -> str:
    age = _safe_str(profile.get("age") or profile.get("age_range") or profile.get("ageRange") or "unknown")
    gender = _safe_str(profile.get("gender") or "unknown")
    mood = _safe_str(profile.get("mood") or profile.get("current_mood") or "neutral")
    topics = _safe_str(profile.get("supportTopics") or profile.get("support_topics") or "general")
    location = _safe_str(profile.get("location") or "unknown")

    return (
        "USER PROFILE:\n"
        f"- AgeRange: {age}\n"
        f"- Gender: {gender}\n"
        f"- CurrentMood: {mood}\n"
        f"- SupportTopics: {topics}\n"
        f"- Location: {location}\n\n"
        + _instruction_block()
    )


def fetch_user_profile_dict(
    db: Session,
    user_id: int,
    fallback_userData: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Öncelik:
    1) UserProfile (varsa)
    2) PersonalityResponse (backward compat)
    3) Flutter userData (fallback)
    4) default unknown
    """

    # 1) UserProfile (varsa)
    try:
        from models import UserProfile  # type: ignore

        p = (
            db.query(UserProfile)
            .filter(UserProfile.user_id == user_id)
            .order_by(desc(UserProfile.id))
            .first()
        )
        if p:
            return {
                "age": getattr(p, "age_range", None) or getattr(p, "age", None) or "unknown",
                "gender": getattr(p, "gender", None) or "unknown",
                "mood": getattr(p, "mood", None) or getattr(p, "current_mood", None) or "neutral",
                "supportTopics": getattr(p, "support_topics", None) or getattr(p, "supportTopics", None) or "general",
                "location": getattr(p, "location", None) or "unknown",
            }
    except Exception:
        pass

    # 2) PersonalityResponse (senin projede kesin var)
    try:
        from models import PersonalityResponse  # type: ignore

        pr = (
            db.query(PersonalityResponse)
            .filter(PersonalityResponse.user_id == user_id)
            .order_by(desc(PersonalityResponse.id))
            .first()
        )
        if pr:
            topics = (_safe_str(getattr(pr, "q4_answer", "")) or "general")
            return {
                "age": getattr(pr, "q1_answer", None) or "unknown",
                "gender": getattr(pr, "q2_answer", None) or "unknown",
                "mood": getattr(pr, "q3_answer", None) or "neutral",
                "supportTopics": topics,
                "location": "unknown",
            }
    except Exception:
        pass

    # 3) Flutter fallback
    if isinstance(fallback_userData, dict) and fallback_userData:
        return {
            "age": fallback_userData.get("age") or fallback_userData.get("ageRange") or "unknown",
            "gender": fallback_userData.get("gender") or "unknown",
            "mood": fallback_userData.get("mood") or "neutral",
            "supportTopics": fallback_userData.get("supportTopics") or fallback_userData.get("support_topics") or "general",
            "location": fallback_userData.get("location") or "unknown",
        }

    # 4) default
    return {
        "age": "unknown",
        "gender": "unknown",
        "mood": "neutral",
        "supportTopics": "general",
        "location": "unknown",
    }


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

    # ✅ Dinamik userData (DB öncelikli)
    user_data = fetch_user_profile_dict(db=db, user_id=current_user.id, fallback_userData=payload.userData)

    # ✅ userContext string (n8n prompt için stabil)
    user_context = build_user_context(user_data)

    try:
        # ✅ ÖNEMLİ: generate_response’e user_id + user_data gönderiyoruz
        reply = await generate_response(
            message=msg,
            history=history,
            user_id=current_user.id,
            user_data=user_data,
            user_context=user_context,
        )
        return ChatResponse(reply=reply)

    except AIClientError as e:
        print("AIClientError:", str(e))
        return ChatResponse(reply="Şu an cevap üretemedim. Bir daha dener misin?")

    except Exception as e:
        print("Unexpected error in /ai/chat:", str(e))
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {str(e)}")
