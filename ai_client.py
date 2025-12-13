import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AI_WEBHOOK_URL = os.getenv("AI_WEBHOOK_URL")


class AIClientError(Exception):
    pass


async def generate_response(
    message: str,
    history: list | None = None,
    user_context: str | None = None,
) -> str:
    if not AI_WEBHOOK_URL:
        raise AIClientError("AI_WEBHOOK_URL tanımlı değil.")

    payload = {
        "message": message,
        "history": history or [],
        "userContext": user_context or "",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(AI_WEBHOOK_URL, json=payload)

        if res.status_code >= 400:
            raise AIClientError(f"AI webhook HTTP {res.status_code}: {res.text}")

        if not res.content or len(res.content) == 0:
            raise AIClientError(
                "AI webhook boş cevap dönüyor (content-length: 0). "
                "n8n workflow sonunda Respond to Webhook JSON dönmeli."
            )

        data = res.json()
        reply = (data.get("reply") or "").strip()

        if not reply:
            raise AIClientError(f"'reply' yok. Gelen JSON: {data}")

        return reply

    except AIClientError:
        raise
    except Exception as e:
        raise AIClientError(f"AI bağlantı hatası: {e}")
