import os
import httpx
from dotenv import load_dotenv

load_dotenv()

AI_WEBHOOK_URL = (os.getenv("AI_WEBHOOK_URL") or "").strip()


class AIClientError(Exception):
    pass


async def generate_response(
    message: str,
    history: list | None = None,
    user_context: str | None = None,
) -> str:
    """
    n8n webhook'a bağlanır.

    Request:
    {
      "message": "...",
      "history": [...],
      "userContext": "..."   # optional
    }

    Response (n8n MUST):
    { "reply": "..." }
    """
    if not AI_WEBHOOK_URL:
        raise AIClientError("AI_WEBHOOK_URL tanımlı değil (Render env).")

    payload = {"message": message, "history": history or []}
    if user_context:
        payload["userContext"] = user_context

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "mindio-backend/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            res = await client.post(AI_WEBHOOK_URL, json=payload, headers=headers)

        # Debug için: status + content-length bilgisini hataya göm
        cl = res.headers.get("content-length", "unknown")

        # 3xx gelirse burada yakala (redirect takip etse bile yine kontrol)
        if res.status_code >= 300:
            raise AIClientError(f"AI webhook HTTP {res.status_code} (content-length={cl}) url={AI_WEBHOOK_URL}")

        if res.status_code >= 400:
            raise AIClientError(f"AI webhook HTTP {res.status_code} (content-length={cl}): {res.text}")

        raw = (res.text or "").strip()
        if not raw:
            raise AIClientError(
                f"AI webhook boş cevap dönüyor (HTTP {res.status_code}, content-length={cl}). "
                f"URL={AI_WEBHOOK_URL} | n8n sonunda Respond to Webhook JSON dönmeli."
            )

        try:
            data = res.json()
        except Exception:
            raise AIClientError(f"AI webhook JSON dönmüyor. HTTP {res.status_code}, content-length={cl}, raw={raw[:300]}")

        reply = (data.get("reply") or "").strip()
        if not reply:
            raise AIClientError(f"AI response içinde 'reply' yok/boş. HTTP {res.status_code}, JSON={data}")

        return reply

    except AIClientError:
        raise
    except Exception as e:
        raise AIClientError(f"AI sunucusuna bağlanırken hata: {str(e)}")
