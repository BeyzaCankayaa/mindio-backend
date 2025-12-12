import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AI_WEBHOOK_URL = os.getenv("AI_WEBHOOK_URL")  # full webhook url


class AIClientError(Exception):
    pass


async def generate_response(message: str, history: list | None = None, user_context: str | None = None) -> str:
    """
    n8n webhook'a bağlanır.
    Request Body:
    {
      "message": "...",
      "history": [...],
      "userContext": "..."   # optional
    }

    Response Body (n8n MUST):
    { "reply": "..." }
    """
    if not AI_WEBHOOK_URL:
        raise AIClientError("AI_WEBHOOK_URL tanımlı değil. .env dosyasını kontrol et.")

    payload = {
        "message": message,
        "history": history or [],
    }
    if user_context:
        payload["userContext"] = user_context

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(AI_WEBHOOK_URL, json=payload)

        # HTTP hata
        if res.status_code >= 400:
            raise AIClientError(f"AI webhook HTTP {res.status_code}: {res.text}")

        # Boş response (senin gördüğün content-length:0 olayı)
        if not res.text or res.text.strip() == "":
            raise AIClientError(
                "AI webhook boş cevap dönüyor (content-length: 0). "
                "n8n workflow sonunda 'Respond to Webhook' JSON body dönmeli."
            )

        # JSON parse
        try:
            data = res.json()
        except Exception:
            raise AIClientError(f"AI webhook JSON dönmüyor. Raw response: {res.text[:300]}")

        reply = (data.get("reply") or "").strip()
        if not reply:
            raise AIClientError(f"AI response içinde 'reply' yok/boş. Gelen JSON: {data}")

        return reply

    except AIClientError:
        raise
    except Exception as e:
        raise AIClientError(f"AI sunucusuna bağlanırken hata: {str(e)}")
