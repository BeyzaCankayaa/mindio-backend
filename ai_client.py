import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AI_BASE_URL = os.getenv("AI_BASE_URL")  # Örn: https://mindio-ai.myserver.com


class AIClientError(Exception):
    pass


async def generate_response(message: str, history: list = None) -> str:
    """
    İlayda'nın AI sunucusuna bağlanan fonksiyon.
    Body = { "message": "...", "history": [...] }
    Response = { "reply": "..." }
    """
    if not AI_BASE_URL:
        raise AIClientError("AI_BASE_URL tanımlı değil. .env dosyasını kontrol et.")

    payload = {
        "message": message,
        "history": history or []
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(f"{AI_BASE_URL}/generate", json=payload)
            res.raise_for_status()

            data = res.json()
            reply = data.get("reply", "").strip()

            if not reply:
                raise AIClientError("AI sunucusu boş yanıt döndürdü.")

            return reply

    except Exception as e:
        raise AIClientError(f"AI sunucusuna bağlanırken hata: {str(e)}")
