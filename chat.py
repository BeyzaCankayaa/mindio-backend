from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_client import generate_response, AIClientError


router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    history: list | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ai(payload: ChatRequest):
    try:
        reply = await generate_response(
            message=payload.message,
            history=payload.history,
        )
        return ChatResponse(reply=reply)

    except AIClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Beklenmeyen hata: {e}")
