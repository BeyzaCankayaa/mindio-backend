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


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Any]] = None


class ChatResponse(BaseModel):
    reply: str


def build_profile_context(personality: Optional[PersonalityResponse]) -> str:
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
        + (
            "EXTRA:\n"
            "- Match tone to CurrentMood (stressed/sad -> calming, grounding).\n"
            "- Use SupportTopics to prioritize suggestions.\n"
        )
    )


def _normalize_history(history: Optional[List[Any]]) -> List[Any]:
    return history if isinstance(history, list) else []


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty.")

    personality = (
        db.query(PersonalityResponse)
        .filter(PersonalityResponse.user_id == current_user.id)
        .order_by(desc(PersonalityResponse.id))
        .first()
    )

    profile_context = build_profile_context(personality)
    history = _normalize_history(payload.history)

    try:
        reply = await generate_response(message=msg, history=history, user_context=profile_context)
        return ChatResponse(reply=reply)

    except AIClientError as e:
        # UX: crash yerine fallback
        print("AIClientError:", str(e))
        return ChatResponse(reply="Şu an cevap üretemedim. Bir daha dener misin?")

    except Exception as e:
        print("Unexpected error in /ai/chat:", str(e))
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {str(e)}")
