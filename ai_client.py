import os
import asyncio
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

    payload = {
        "message": message,
        "history": history or [],
    }
    if user_context:
        payload["userContext"] = user_context

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "mindio-backend/1.0",
    }

    # Render + n8n bazen 1-2 istekte boş dönebiliyor => retry
    max_attempts = 3
    backoff_seconds = 1.2

    timeout = httpx.Timeout(
        connect=10.0,
        read=120.0,   # LLM/n8n gecikirse burada patlamasın
        write=30.0,
        pool=10.0,
    )

    last_err: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                res = await client.post(AI_WEBHOOK_URL, json=payload, headers=headers)

            # ÖNEMLİ: header değil gerçek body ölç
            body_bytes = res.content or b""
            body_len = len(body_bytes)

            # HTTP hata
            if res.status_code >= 400:
                raise AIClientError(
                    f"AI webhook HTTP {res.status_code} (body_len={body_len}) url={AI_WEBHOOK_URL} "
                    f"resp={body_bytes[:300]!r}"
                )

            # Boş body (asıl problem)
            if body_len == 0:
                raise AIClientError(
                    f"AI webhook boş cevap dönüyor (HTTP {res.status_code}, body_len=0). "
                    f"URL={AI_WEBHOOK_URL} | n8n sonunda Respond to Webhook JSON dönmeli."
                )

            # Decode
            raw = body_bytes.decode("utf-8", errors="replace").strip()
            if not raw:
                raise AIClientError(
                    f"AI webhook raw boş (HTTP {res.status_code}, body_len={body_len}). "
                    f"raw_preview={body_bytes[:80]!r}"
                )

            # JSON parse
            try:
                data = res.json()
            except Exception:
                raise AIClientError(
                    f"AI webhook JSON dönmüyor. HTTP {res.status_code}, body_len={body_len}, raw={raw[:300]}"
                )

            reply = (data.get("reply") or "").strip()
            if not reply:
                raise AIClientError(
                    f"AI response içinde 'reply' yok/boş. HTTP {res.status_code}, body_len={body_len}, JSON={data}"
                )

            return reply

        except (AIClientError, httpx.HTTPError, asyncio.TimeoutError) as e:
            last_err = e

            # son deneme değilse retry
            if attempt < max_attempts:
                await asyncio.sleep(backoff_seconds * attempt)
                continue

            # son denemede patlat
            raise AIClientError(f"AI çağrısı başarısız (attempt={attempt}/{max_attempts}): {str(e)}") from e

        except Exception as e:
            # beklenmeyen
            raise AIClientError(f"AI sunucusuna bağlanırken beklenmeyen hata: {str(e)}") from e

    # teorik olarak buraya düşmez
    raise AIClientError(f"AI çağrısı başarısız: {str(last_err)}")
