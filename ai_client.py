import os
import json
import asyncio
import logging
import uuid
from typing import Any, Optional, List, Dict, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

AI_WEBHOOK_URL = (os.getenv("AI_WEBHOOK_URL") or "").strip()

# Turn on verbose payload logs only when you want:
# Render env: AI_DEBUG=1
AI_DEBUG = (os.getenv("AI_DEBUG") or "0").strip() in ("1", "true", "True", "yes", "YES")

logger = logging.getLogger("mindio.ai_client")


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


def _safe_preview(s: str, n: int = 120) -> str:
    s = (s or "").replace("\n", " ").replace("\r", " ").strip()
    if len(s) <= n:
        return s
    return s[:n] + "…"


def _summarize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Do NOT log PII. Only summarize keys + small safe preview for primitive values.
    """
    keys = list(user_data.keys())
    sample: Dict[str, Any] = {}
    for k in keys[:10]:
        v = user_data.get(k)
        if isinstance(v, (str, int, float, bool)) or v is None:
            if isinstance(v, str):
                sample[k] = _safe_preview(v, 40)
            else:
                sample[k] = v
        else:
            sample[k] = f"<{type(v).__name__}>"
    return {
        "hasUserData": bool(user_data),
        "userDataKeys": keys[:30],
        "userDataSample": sample,
    }


def _debug_log_payload(payload: Dict[str, Any], request_id: str) -> None:
    """
    Logs minimal + safe debug, not the full payload.
    """
    try:
        uctx = payload.get("userContext") or ""
        udata = payload.get("userData") if isinstance(payload.get("userData"), dict) else {}
        logger.info(
            "[AI_DEBUG][%s] OUTGOING payload summary: message_len=%s history_len=%s userContext_len=%s userContext_preview=%r userData=%s",
            request_id,
            len((payload.get("message") or "")),
            len(payload.get("history") or []),
            len(str(uctx)),
            _safe_preview(str(uctx), 120),
            _summarize_user_data(udata),
        )
    except Exception as e:
        logger.warning("[AI_DEBUG][%s] Could not summarize payload: %s", request_id, str(e))


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

    request_id = uuid.uuid4().hex[:10]

    # ✅ payload: root + nested (n8n bazı yerlerde body/data karışabiliyor)
    payload: Dict[str, Any] = {
        "message": msg,
        "history": hist,

        # ✅ BOTH CONTRACTS
        "userContext": uctx,      # string
        "userData": udata,        # object

        # ✅ ALSO PROVIDE nested data field (safety for n8n mappings)
        "data": {
            "message": msg,
            "history": hist,
            "userContext": uctx,
            "userData": udata,
        },

        # ✅ debug marker (n8n kız görsün gerçekten geliyor mu)
        "meta": {
            "requestId": request_id,
            "source": "mindio-backend",
            "hasUserContext": bool(uctx),
            "hasUserData": bool(udata),
            "userDataKeys": list(udata.keys())[:30],
        },
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "mindio-backend/1.0",
        "X-Request-Id": request_id,
    }

    max_attempts = 3
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)

    if AI_DEBUG:
        _debug_log_payload(payload, request_id)
        logger.info("[AI_DEBUG][%s] POST -> %s", request_id, AI_WEBHOOK_URL)

    last_err: Optional[Exception] = None

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                res = await client.post(AI_WEBHOOK_URL, json=payload, headers=headers)

                body_bytes = res.content or b""
                body_len = len(body_bytes)

                if AI_DEBUG:
                    logger.info(
                        "[AI_DEBUG][%s] attempt=%s status=%s body_len=%s content_type=%r",
                        request_id,
                        attempt,
                        res.status_code,
                        body_len,
                        res.headers.get("content-type"),
                    )

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

                # JSON değilse plain text kabul
                try:
                    data = res.json()
                except json.JSONDecodeError:
                    if AI_DEBUG:
                        logger.info("[AI_DEBUG][%s] Response is plain text, returning raw.", request_id)
                    return raw

                reply = _extract_reply(data)
                if not reply:
                    # debug: show keys only, not whole json
                    keys = list(data.keys()) if isinstance(data, dict) else [type(data).__name__]
                    raise AIClientError(
                        "AI response içinde reply/textResponse/text yok. "
                        f"HTTP {res.status_code}, body_len={body_len}, json_keys={keys[:50]}"
                    )

                return reply

            except (AIClientError, httpx.HTTPError, asyncio.TimeoutError) as e:
                last_err = e
                if AI_DEBUG:
                    logger.warning("[AI_DEBUG][%s] attempt=%s failed: %s", request_id, attempt, str(e))

                if attempt < max_attempts:
                    await asyncio.sleep(1.0 * attempt)
                    continue

                raise AIClientError(
                    f"AI çağrısı başarısız (attempt={attempt}/{max_attempts}): {str(e)}"
                ) from e

            except Exception as e:
                if AI_DEBUG:
                    logger.exception("[AI_DEBUG][%s] Unexpected error", request_id)
                raise AIClientError(f"AI beklenmeyen hata: {str(e)}") from e

    raise AIClientError(f"AI çağrısı başarısız: {str(last_err)}")
