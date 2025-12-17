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
    user_data: Optional[Dict[str, Any]] = None,
) -> str:
    if not AI_WEBHOOK_URL:
        raise AIClientError("AI_WEBHOOK_URL tanımlı değil (Render env).")

    # sanitize
    msg = (message or "").strip()
    hist = history if isinstance(history, list) else []
    uctx = (user_context or "").strip()
    udata = user_data if isinstance(user_data, dict) else {}

    # ✅ payload: root + nested (n8n bazı yerlerde body/data karışabiliyor)
    payload: Dict[str, Any] = {
        "message": msg,
        "history": hist,

        # ✅ BOTH CONTRACTS
        "userContext": uctx,      # string
        "userData": udata,        # object (Amine prompt)

        # ✅ ALSO PROVIDE nested data field (safety for n8n mappings)
        "data": {
            "message": msg,
            "history": hist,
            "userContext": uctx,
            "userData": udata,
        },

        # ✅ debug marker (kız görsün gerçekten geliyor mu)
        "meta": {
            "source": "mindio-backend",
            "hasUserData": bool(udata),
            "userDataKeys": list(udata.keys())[:30],
        },
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "mindio-backend/1.0",
    }

    max_attempts = 3
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)

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
                    return raw  # plain text döndüyse kabul

                reply = _extract_reply(data)
                if not reply:
                    raise AIClientError(
                        "AI response içinde reply/textResponse/text yok. "
                        f"HTTP {res.status_code}, body_len={body_len}, json_type={type(data)}"
                    )

                return reply

            except (AIClientError, httpx.HTTPError, asyncio.TimeoutError) as e:
                last_err = e
                if attempt < max_attempts:
                    await asyncio.sleep(1.0 * attempt)
                    continue
                raise AIClientError(
                    f"AI çağrısı başarısız (attempt={attempt}/{max_attempts}): {str(e)}"
                ) from e

            except Exception as e:
                raise AIClientError(f"AI beklenmeyen hata: {str(e)}") from e

    raise AIClientError(f"AI çağrısı başarısız: {str(last_err)}")
