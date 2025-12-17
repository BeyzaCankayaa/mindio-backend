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

    # Flutter geçici yolluyor olabilir (DB boşsa fallback için)
    userData: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str


def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    return history if isinstance(history, list) else []


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def build_user_data_from_profile_dict(profile: Dict[str, Any]) -> Dict[str, Any]:
    # ✅ n8n'de Amine'nin beklediği obje formatı
    return {
        "userId": _safe_str(profile.get("userId") or profile.get("user_id") or profile.get("id") or ""),
        "age": _safe_str(profile.get("age") or profile.get("age_range") or profile.get("ageRange") or "unknown"),
        "gender": _safe_str(profile.get("gender") or "unknown"),
        "mood": _safe_str(profile.get("mood") or profile.get("current_mood") or "neutral"),
        "supportTopics": _safe_str(profile.get("supportTopics") or profile.get("support_topics") or "general"),
        "location": _safe_str(profile.get("location") or "unknown"),
    }


def build_user_context_from_user_data(user_data: Dict[str, Any]) -> str:
    # ✅ n8n string isteyen path'ler için de hazır dursun
    age = _safe_str(user_data.get("age") or "unknown")
    gender = _safe_str(user_data.get("gender") or "unknown")
    mood = _safe_str(user_data.get("mood") or "neutral")
    topics = _safe_str(user_data.get("supportTopics") or "general")
    location = _safe_str(user_data.get("location") or "unknown")

    return (
        f"Age: {age}, Gender: {gender}, Mood: {mood}, Topics: {topics}, Location: {location} | "
        "INSTRUCTION: Speak Turkish. Short and practical. No medical diagnosis. "
        "If severe/persistent, suggest professional support."
    )


def fetch_user_data(db: Session, user_id: int, fallback_userData: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Öncelik:
    1) UserProfile (varsa)
    2) PersonalityResponse (varsa)
    3) Flutter payload.userData (fallback)
    4) unknown
    """
    # 1) UserProfile varsa
    try:
        from models import UserProfile  # type: ignore
        profile_obj = (
            db.query(UserProfile)
            .filter(UserProfile.user_id == user_id)
            .order_by(desc(UserProfile.id))
            .first()
        )
        if profile_obj:
            profile_dict = {
                "userId": str(user_id),
                "age": getattr(profile_obj, "age_range", None) or getattr(profile_obj, "age", None),
                "gender": getattr(profile_obj, "gender", None),
                "mood": getattr(profile_obj, "mood", None) or getattr(profile_obj, "current_mood", None),
                "supportTopics": getattr(profile_obj, "support_topics", None) or getattr(profile_obj, "supportTopics", None),
                "location": getattr(profile_obj, "location", None) or "unknown",
            }
            return build_user_data_from_profile_dict(profile_dict)
    except Exception:
        pass

    # 2) PersonalityResponse backward compat
    try:
        from models import PersonalityResponse  # type: ignore
        p = (
            db.query(PersonalityResponse)
            .filter(PersonalityResponse.user_id == user_id)
            .order_by(desc(PersonalityResponse.id))
            .first()
        )
        if p:
            topics = (_safe_str(getattr(p, "q4_answer", "")) or "general wellbeing")
            profile_dict = {
                "userId": str(user_id),
                "age": getattr(p, "q1_answer", None) or "unknown",
                "gender": getattr(p, "q2_answer", None) or "unknown",
                "mood": getattr(p, "q3_answer", None) or "neutral",
                "supportTopics": topics,
                "location": "unknown",
            }
            return build_user_data_from_profile_dict(profile_dict)
    except Exception:
        pass

    # 3) Flutter fallback
    if isinstance(fallback_userData, dict) and fallback_userData:
        # userId yoksa ekle
        if "userId" not in fallback_userData and "user_id" not in fallback_userData:
            fallback_userData = {**fallback_userData, "userId": str(user_id)}
        return build_user_data_from_profile_dict(fallback_userData)

    # 4) default unknown
    return build_user_data_from_profile_dict({"userId": str(user_id)})


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

    # ✅ NEW: DB’den userData üret, gerekirse payload.userData fallback
    user_data = fetch_user_data(db=db, user_id=current_user.id, fallback_userData=payload.userData)

    # ✅ userContext string’i de üret (ikisini birden gönderiyoruz)
    user_context = build_user_context_from_user_data(user_data)

    try:
        reply = await generate_response(
            message=msg,
            history=history,
            user_context=user_context,
            user_data=user_data,   # ✅ NEW
        )
        return ChatResponse(reply=reply)

    except AIClientError as e:
        print("AIClientError:", str(e))
        return ChatResponse(reply="Şu an cevap üretemedim. Bir daha dener misin?")

    except Exception as e:
        print("Unexpected error in /ai/chat:", str(e))
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {str(e)}")
