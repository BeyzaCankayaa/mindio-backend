# chat.py
from __future__ import annotations

import os
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

    topics = (personality.q4_answer or "").strip() or "General wellbeing"

    return (
        "USER PROFILE:\n"
        f"- AgeRange: {personality.q1_answer}\n"
        f"- Gender: {personality.q2_answer}\n"
        f"- CurrentMood: {personality.q3_answer}\n"
        f"- SupportTopics: {topics}\n\n"
        + instruction
        + "EXTRA:\n"
          "- Match tone to CurrentMood (stressed/sad -> calming, grounding).\n"
          "- Use SupportTopics to prioritize suggestions.\n"
    )


def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    if isinstance(history, list):
        return history
    return []


def _safe_reply_or_fallback(raw: Any) -> str:
    """
    n8n/AI bazen boş dönebiliyor. Burada crash etme -> fallback dön.
    """
    if raw is None:
        return "Şu an cevap üretemedim. Bir daha dener misin?"

    if isinstance(raw, dict):
        val = raw.get("reply") or raw.get("text") or raw.get("message")
        if isinstance(val, str) and val.strip():
            return val.strip()
        return "Şu an cevap üretemedim. Bir daha dener misin?"

    if isinstance(raw, str):
        if raw.strip():
            return raw.strip()
        return "Şu an cevap üretemedim. Bir daha dener misin?"

    return "Şu an cevap üretemedim. Bir daha dener misin?"


# ===================== ROUTE =====================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )

    # DEBUG: Render log'da hangi webhook'a gittiğini gör
    print("AI_WEBHOOK_URL =", os.getenv("AI_WEBHOOK_URL"))

    personality = (
        db.query(PersonalityResponse)
        .filter(PersonalityResponse.user_id == current_user.id)
        .order_by(desc(PersonalityResponse.id))
        .first()
    )

    profile_context = build_profile_context(personality)
    history = _normalize_history(payload.history)

    try:
        raw_reply = await generate_response(
            message=msg,
            history=history,
            user_context=profile_context,
        )
        return ChatResponse(reply=_safe_reply_or_fallback(raw_reply))

    except AIClientError as e:
        # burada 502 fırlatmak yerine fallback dönüyoruz (UX kurtar)
        # ama log'a yaz ki takip edelim
        print("AIClientError:", str(e))
        return ChatResponse(reply="Şu an cevap üretemedim. Bir daha dener misin?")

    except Exception as e:
        print("Unexpected error in /ai/chat:", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Beklenmeyen hata: {str(e)}",
        )
