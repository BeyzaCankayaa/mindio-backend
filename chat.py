from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import User
from auth import get_current_user

from ai_client import generate_response, AIClientError

router = APIRouter(prefix="/ai", tags=["AI"])


# =========================
# Schemas
# =========================
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Any]] = None
    userData: Optional[Dict[str, Any]] = None  # Flutter fallback


class ChatResponse(BaseModel):
    reply: str


# =========================
# Helpers
# =========================
def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    return history if isinstance(history, list) else []


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _extract_age_number(age_raw: str) -> Optional[int]:
    m = re.search(r"\d+", age_raw or "")
    if m:
        try:
            return int(m.group(0))
        except Exception:
            return None
    return None


def _apply_daily_override_from_mood_table(
    db: Session,
    user_id: int,
    profile_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Daily girişte alınan mood/supportTopics’in chat’e yansıması için:
    Mood tablosundan en son kaydı çekip profile_dict üstüne override eder.

    Sizin projede model adı değişebilir diye 3 olası adı dener:
    Mood, MoodEntry, UserMood
    """
    mood_model = None
    for name in ("Mood", "MoodEntry", "UserMood"):
        try:
            from models import __dict__ as models_dict  # type: ignore
            mood_model = models_dict.get(name)
            if mood_model is not None:
                break
        except Exception:
            mood_model = None

    if mood_model is None:
        return profile_dict

    try:
        last_row = (
            db.query(mood_model)
            .filter(getattr(mood_model, "user_id") == user_id)
            .order_by(desc(getattr(mood_model, "id")))
            .first()
        )
        if not last_row:
            return profile_dict

        # DB alan adları: mood, note (openapi MoodCreate: mood + note)
        mood_val = getattr(last_row, "mood", None)
        note_val = getattr(last_row, "note", None)

        if mood_val:
            profile_dict["mood"] = mood_val

        # Biz note'u "daily supportTopics" gibi kullanıyoruz (şimdilik)
        if note_val:
            profile_dict["supportTopics"] = note_val

        return profile_dict
    except Exception:
        return profile_dict


# =========================
# UserData builders
# =========================
def build_user_data_from_profile_dict(profile: Dict[str, Any]) -> Dict[str, Any]:
    age_raw = _safe_str(
        profile.get("age")
        or profile.get("age_range")
        or profile.get("ageRange")
        or "unknown"
    )
    age_num = _extract_age_number(age_raw)

    return {
        "userId": _safe_str(profile.get("userId") or profile.get("user_id") or profile.get("id") or ""),
        "age": age_raw,          # "45+"
        "ageRange": age_raw,     # explicit
        "ageNumber": age_num,    # 45  ⭐ KRİTİK
        "gender": _safe_str(profile.get("gender") or "unknown"),
        "mood": _safe_str(profile.get("mood") or profile.get("current_mood") or "neutral"),
        "supportTopics": _safe_str(profile.get("supportTopics") or profile.get("support_topics") or "general"),
        "location": _safe_str(profile.get("location") or "unknown"),
    }


def build_user_context_from_user_data(user_data: Dict[str, Any]) -> str:
    # n8n string isteyen path'ler için
    age = _safe_str(user_data.get("age") or "unknown")
    gender = _safe_str(user_data.get("gender") or "unknown")
    mood = _safe_str(user_data.get("mood") or "neutral")
    topics = _safe_str(user_data.get("supportTopics") or "general")
    location = _safe_str(user_data.get("location") or "unknown")

    return (
        f"Age: {age}, Gender: {gender}, Mood: {mood}, "
        f"Topics: {topics}, Location: {location} | "
        "INSTRUCTION: Speak Turkish. Short and practical. No medical diagnosis."
    )


# =========================
# Fetch user data
# =========================
def fetch_user_data(
    db: Session,
    user_id: int,
    fallback_userData: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Öncelik:
    1) UserProfile (sabit onboarding)
       + DAILY override: mood tablosundan en güncel mood/supportTopics (her gün giriş)
    2) PersonalityResponse (legacy)
       + DAILY override
    3) Flutter payload.userData (fallback)
    4) unknown
    """
    # 1) UserProfile
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

            # ✅ DAILY OVERRIDE (mood/add’dan gelen en güncel değerler)
            profile_dict = _apply_daily_override_from_mood_table(db=db, user_id=user_id, profile_dict=profile_dict)

            return build_user_data_from_profile_dict(profile_dict)
    except Exception:
        pass

    # 2) PersonalityResponse (legacy)
    try:
        from models import PersonalityResponse  # type: ignore
        p = (
            db.query(PersonalityResponse)
            .filter(PersonalityResponse.user_id == user_id)
            .order_by(desc(PersonalityResponse.id))
            .first()
        )
        if p:
            profile_dict = {
                "userId": str(user_id),
                "age": getattr(p, "q1_answer", None) or "unknown",
                "gender": getattr(p, "q2_answer", None) or "unknown",
                "mood": getattr(p, "q3_answer", None) or "neutral",
                "supportTopics": getattr(p, "q4_answer", None) or "general",
                "location": "unknown",
            }

            # ✅ DAILY OVERRIDE yine uygula
            profile_dict = _apply_daily_override_from_mood_table(db=db, user_id=user_id, profile_dict=profile_dict)

            return build_user_data_from_profile_dict(profile_dict)
    except Exception:
        pass

    # 3) Flutter fallback
    if isinstance(fallback_userData, dict) and fallback_userData:
        if "userId" not in fallback_userData and "user_id" not in fallback_userData:
            fallback_userData = {**fallback_userData, "userId": str(user_id)}
        return build_user_data_from_profile_dict(fallback_userData)

    # 4) Default
    return build_user_data_from_profile_dict({"userId": str(user_id)})


# =========================
# Endpoint
# =========================
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

    user_data = fetch_user_data(
        db=db,
        user_id=current_user.id,
        fallback_userData=payload.userData,
    )

    # (opsiyonel) userContext — n8n bazı mappinglerde kullanabilir
    user_context = build_user_context_from_user_data(user_data)

    try:
        reply = await generate_response(
            message=msg,
            history=history,
            user_context=user_context,
            user_data=user_data,
        )

        # =========================
        # HARD FILTER for 45+ (UI güvenliği)
        # =========================
        age_num = user_data.get("ageNumber")
        if isinstance(age_num, int) and age_num >= 45:
            reply = re.sub(r"\b(dostum|kanka)\b[,\s]*", "", reply, flags=re.IGNORECASE)
            reply = re.sub(r"[\U0001F300-\U0001FAFF]+", "", reply)
            reply = re.sub(r"[ \t]{2,}", " ", reply).strip()

        return ChatResponse(reply=reply)

    except AIClientError as e:
        print("AIClientError:", str(e))
        return ChatResponse(reply="Şu an cevap üretemedim. Bir daha dener misin?")

    except Exception as e:
        print("Unexpected error in /ai/chat:", str(e))
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {str(e)}")
