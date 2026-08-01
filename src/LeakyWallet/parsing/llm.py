import datetime
import hashlib
import json

import httpx
from pydantic import ValidationError

from LeakyWallet.config import get_settings
from LeakyWallet.logging import get_logger
from LeakyWallet.parsing.schemas import LLMReceiptFields
from LeakyWallet.redis import get_redis

logger = get_logger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_CACHE_PREFIX = "llm:receipt-cache:"
_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
_LIMIT_PREFIX = "llm:daily-calls:"
_LIMIT_TTL_SECONDS = 25 * 60 * 60  # с запасом за сутки, чтобы ключ не истёк раньше полуночи

_SYSTEM_PROMPT = """Ты извлекаешь данные из письма о списании за подписку.
Тебе присылают тему и короткий фрагмент письма. Определи:
- is_charge: true, если это подтверждение оплаты/списания денег за подписку или сервис, иначе false.
- amount: сумма списания числом (например 799.00), только если is_charge=true, иначе null.
- currency: код валюты ISO 4217 (RUB, USD, EUR и т.д.), только если is_charge=true, иначе null.
- period: периодичность, одно из "weekly", "monthly", "quarterly", "yearly", если явно понятна \
из текста, иначе null.

Ответь СТРОГО одним JSON-объектом, без пояснений, без markdown-разметки, без текста до или после:
{"is_charge": true|false, "amount": число или null, "currency": строка или null, \
"period": строка или null}"""

_ERRORS = (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, ValidationError)


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def _cache_key(normalized_text: str) -> str:
    digest = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
    return f"{_CACHE_PREFIX}{digest}"


def _strip_code_fence(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
        content = content.removesuffix("```").strip()
    return content


async def _within_daily_limit(user_id: int) -> bool:
    settings = get_settings()
    redis = get_redis()
    today = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    key = f"{_LIMIT_PREFIX}{user_id}:{today}"

    calls = await redis.incr(key)
    if calls == 1:
        await redis.expire(key, _LIMIT_TTL_SECONDS)
    return bool(calls <= settings.llm_daily_limit_per_user)


async def _call_openrouter(normalized_text: str) -> LLMReceiptFields | None:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json={
                    "model": settings.openrouter_model,
                    "temperature": 0,
                    "max_tokens": 300,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": normalized_text},
                    ],
                },
            )
            response.raise_for_status()
            payload = response.json()

        content = payload["choices"][0]["message"]["content"]
        data = json.loads(_strip_code_fence(content))
        return LLMReceiptFields.model_validate(data)
    except _ERRORS:
        logger.warning("llm extraction failed, treating message as unparsed")
        return None


async def extract_with_llm(text: str, *, user_id: int) -> LLMReceiptFields | None:
    settings = get_settings()
    if not settings.openrouter_api_key:
        return None

    normalized = _normalize(text)
    redis = get_redis()
    cache_key = _cache_key(normalized)

    cached = await redis.get(cache_key)
    if cached is not None:
        return LLMReceiptFields.model_validate_json(cached)

    if not await _within_daily_limit(user_id):
        logger.info("llm daily limit reached", user_id=user_id)
        return None

    fields = await _call_openrouter(normalized)
    if fields is None:
        return None

    await redis.set(cache_key, fields.model_dump_json(), ex=_CACHE_TTL_SECONDS)
    return fields
