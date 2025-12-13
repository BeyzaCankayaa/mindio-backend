# chat.py
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models import PersonalityResponse, User
from auth import get_current_user

from ai_client import generate_response, AIClientError

router = APIRouter(prefix="/ai", tags=["AI"])


# ===================== SCHEMAS =====================

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Any]] = None  # n8n tarafına aynen geçilecek


class ChatResponse(BaseModel):
    reply: str


# ===================== HELPERS =====================

def build_profile_context(personality: Optional[PersonalityResponse]) -> str:
    """
    AI'ye gönderilecek userContext metni.
    Personality yoksa da stabil bir fallback context üretir.
    """
    # Ortak talimat bloğu (her durumda)
    instruction = (
        "INSTRUCTION:\n"
        "- Speak Turkish.\n"
        "- Short, clear, step-by-step.\n"
        "- Be supportive and practical.\n"
        "- Avoid medical diagnosis.\n"
        "- If symptoms are severe or persistent, suggest seeking a professional.\n"
    )

    if not personality:
        return (
            "USER PROFILE:\n"
            "- AgeRange: Unknown\n"
            "- Gender: Unknown\n"
            "- CurrentMood: Neutral\n"
            "- SupportTopics: General wellbeing\n\n"
            + instruction
        )

    topics = (personality.q4_answer or "").strip()
    if not topics:
        topics = "General wellbeing"

    return (
        "USER PROFILE:\n"
        f"- AgeRange: {personality.q1_answer}\n"
        f"- Gender: {personality.q2_answer}\n"
        f"- CurrentMood: {personality.q3_answer}\n"
        f"- SupportTopics: {topics}\n\n"
        + instruction +
        "EXTRA:\n"
        "- Match tone to CurrentMood (stressed/sad -> calming, grounding).\n"
        "- Use SupportTopics to prioritize suggestions.\n"
    )


def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    """
    history None/garip tip gelirse crash olmasın diye normalize eder.
    """
    if history is None:
        return []
    if isinstance(history, list):
        return history
    return []


def _validate_reply(reply: Any) -> str:
    """
    AI'den gelen reply'ı güvenli hale getirir.
    """
    if reply is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI boş cevap döndü (reply=None).",
        )

    # bazı client'lar dict döndürebilir: {"reply": "..."} gibi
    if isinstance(reply, dict):
        val = reply.get("reply") or reply.get("text") or reply.get("message")
        if isinstance(val, str) and val.strip():
            return val.strip()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI beklenen formatta dönmedi (dict içinde reply/text yok).",
        )

    if isinstance(reply, str):
        if not reply.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI boş string döndü (reply='').",
            )
        return reply.strip()

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"AI beklenmeyen tip döndü: {type(reply)}",
    )


# ===================== ROUTE =====================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # basic input check
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    # personality: en son kaydı çek
    personality = (
        db.query(PersonalityResponse)
        .filter(PersonalityResponse.user_id == current_user.id)
        .order_by(desc(PersonalityResponse.id))
        .first()
    )

    profile_context = build_profile_context(personality)
    history = _normalize_history(payload.history)

    try:
        # ai_client.generate_response bu imzayla çalışıyor varsayımı:
        # await generate_response(message=..., history=[...], user_context="...")
        raw_reply = await generate_response(
            message=msg,
            history=history,
            user_context=profile_context,
        )

        safe_reply = _validate_reply(raw_reply)
        return ChatResponse(reply=safe_reply)

    except AIClientError as e:
        # AI client kendi hatası (timeout, empty body vs.)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AIClientError: {str(e)}",
        )

    except HTTPException:
        # yukarıdaki _validate_reply gibi yerlerden gelen kontrollü hatalar
        raise

    except Exception as e:
        # beklenmeyen
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Beklenmeyen hata: {str(e)}",
        )
