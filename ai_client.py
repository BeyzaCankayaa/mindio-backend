import os
import json
import asyncio
from typing import Any, Optional, List, Dict

import httpx
from dotenv import load_dotenv

load_dotenv()

AI_WEBHOOK_URL = (os.getenv("AI_WEBHOOK_URL") or "").strip()


class AIClientError(Exception):
    pass


def _extract_reply(data: Any) -> Optional[str]:
    if data is None:
        return None

    if isinstance(data, str):
        return data.strip() or None

    if isinstance(data, dict):
        for k in ["reply", "textResponse", "text", "output", "message"]:
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

        nested = data.get("data")
        if isinstance(nested, dict):
            for k in ["reply", "textResponse", "text", "output", "message"]:
                v = nested.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    if isinstance(data, list) and data:
        return _extract_reply(data[0])

    return None


async def generate_response(
    message: str,
    history: Optional[List[Any]] = None,
    user_context: Optional[str] = None,
    user_id: Optional[int] = None,                 # ✅ NEW (optional)
    user_data: Optional[Dict[str, Any]] = None,    # ✅ NEW (optional)
    **kwargs,                                      # ✅ tolerate extra args
) -> str:
    if not AI_WEBHOOK_URL:
        raise AIClientError("AI_WEBHOOK_URL tanımlı değil (Render env).")

    # ✅ payload: n8n tarafı neyi kullanıyorsa onu gönderebiliriz
    payload: Dict[str, Any] = {
        "message": message,
        "history": history or [],
        "userContext": (user_context or "").strip(),  # n8n string bekliyor
    }

    # opsiyonel alanlar (n8n isterse kullanır, istemezse görmezden gelir)
    if user_id is not None:
        payload["userId"] = int(user_id)
    if isinstance(user_data, dict) and user_data:
        payload["userData"] = user_data

    # ekstra gelen kwargs varsa ve çakışmıyorsa payload'a ekleyelim (safe)
    # örn: some_flow_flag=True gibi
    for k, v in kwargs.items():
        if k not in payload and v is not None:
            payload[k] = v

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "mindio-backend/1.0",
    }

    max_attempts = 3
    backoff_seconds = 1.0

    timeout = httpx.Timeout(
        connect=10.0,
        read=120.0,
        write=30.0,
        pool=10.0,
    )

    last_err: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                res = await client.post(AI_WEBHOOK_URL, json=payload, headers=headers)

                body_bytes = res.content or b""
                body_len = len(body_bytes)

                if res.status_code >= 400:
                    raise AIClientError(
                        f"AI webhook HTTP {res.status_code} (body_len={body_len}) url={AI_WEBHOOK_URL} "
                        f"resp_preview={body_bytes[:300]!r}"
                    )

                if body_len == 0:
                    raise AIClientError(
                        f"AI webhook boş cevap dönüyor (HTTP {res.status_code}, body_len=0). "
                        f"URL={AI_WEBHOOK_URL} | n8n her path'te Respond to Webhook JSON dönmeli."
                    )

                raw = body_bytes.decode("utf-8", errors="replace").strip()
                if not raw:
                    raise AIClientError(
                        f"AI webhook raw boş (HTTP {res.status_code}, body_len={body_len}). "
                        f"raw_preview={body_bytes[:80]!r}"
                    )

                try:
                    data = res.json()
                except json.JSONDecodeError:
                    # JSON değilse plain text döndüyse onu reply say
                    return raw

                reply = _extract_reply(data)
                if not reply:
                    raise AIClientError(
                        f"AI response içinde reply/textResponse/text yok. "
                        f"HTTP {res.status_code}, body_len={body_len}, JSON_keys="
                        f"{list(data.keys()) if isinstance(data, dict) else type(data)}"
                    )

                return reply

            except (AIClientError, httpx.HTTPError, asyncio.TimeoutError) as e:
                last_err = e
                if attempt < max_attempts:
                    await asyncio.sleep(backoff_seconds * attempt)
                    continue
                raise AIClientError(
                    f"AI çağrısı başarısız (attempt={attempt}/{max_attempts}): {str(e)}"
                ) from e

            except Exception as e:
                raise AIClientError(f"AI beklenmeyen hata: {str(e)}") from e

    raise AIClientError(f"AI çağrısı başarısız: {str(last_err)}")
