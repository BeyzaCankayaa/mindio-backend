from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_client import generate_response, AIClientError

from database import get_db
from models import PersonalityResponse, User
from auth import get_current_user  # <- auth.py içinde get_current_user var diye varsayıyorum

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    history: list | None = None


class ChatResponse(BaseModel):
    reply: str


def build_profile_context(personality: PersonalityResponse | None) -> str:
    """
    AI'ye en baştan eklenecek profil talimat bloğu.
    personality yoksa fallback kullanır.
    """
    if not personality:
        return (
            "USER PROFILE:\n"
            "- AgeRange: Unknown\n"
            "- Gender: Unknown\n"
            "- CurrentMood: Neutral\n"
            "- SupportTopics: General wellbeing\n\n"
            "INSTRUCTION:\n"
            "- Speak Turkish.\n"
            "- Short, clear, step-by-step.\n"
            "- Be supportive, avoid medical diagnosis.\n"
        )

    topics = personality.q4_answer or ""
    # q4_answer DB'de "Stres Yönetimi, Uyku Düzeni" gibi string tutuluyor zaten

    return (
        "USER PROFILE:\n"
        f"- AgeRange: {personality.q1_answer}\n"
        f"- Gender: {personality.q2_answer}\n"
        f"- CurrentMood: {personality.q3_answer}\n"
        f"- SupportTopics: {topics}\n\n"
        "INSTRUCTION:\n"
        "- Speak Turkish.\n"
        "- Match tone to CurrentMood (stressed/sad -> calming, grounding).\n"
        "- Give practical, small steps.\n"
        "- Use SupportTopics to prioritize suggestions.\n"
        "- Avoid medical diagnosis; suggest seeking a professional for severe symptoms.\n"
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        personality = (
            db.query(PersonalityResponse)
            .filter(PersonalityResponse.user_id == current_user.id)
            .order_by(PersonalityResponse.id.desc())
            .first()
        )

        profile_context = build_profile_context(personality)

        reply = await generate_response(
            message=payload.message,
            history=payload.history or [],     # history aynen geç
            user_context=profile_context,      # n8n userContext buradan
        )

        return ChatResponse(reply=reply)

    except AIClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {e}")
