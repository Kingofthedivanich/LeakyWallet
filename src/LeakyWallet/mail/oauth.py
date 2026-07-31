import secrets
import urllib.parse
from dataclasses import dataclass

import httpx

from LeakyWallet.config import get_settings
from LeakyWallet.redis import get_redis

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"

STATE_TTL_SECONDS = 600
STATE_REDIS_PREFIX = "oauth:state:"


@dataclass(frozen=True)
class TokenResponse:
    access_token: str
    refresh_token: str | None
    expires_in: int


async def create_auth_url(user_id: int) -> str:
    settings = get_settings()
    state = secrets.token_urlsafe(32)

    redis = get_redis()
    await redis.set(f"{STATE_REDIS_PREFIX}{state}", str(user_id), ex=STATE_TTL_SECONDS)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": GMAIL_READONLY_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def pop_user_id_for_state(state: str) -> int | None:
    redis = get_redis()
    value = await redis.getdel(f"{STATE_REDIS_PREFIX}{state}")
    if value is None:
        return None
    return int(value)


def _parse_token_response(
    payload: dict[str, object], *, fallback_refresh_token: str | None
) -> TokenResponse:
    refresh_token = payload.get("refresh_token")
    return TokenResponse(
        access_token=str(payload["access_token"]),
        refresh_token=str(refresh_token) if refresh_token else fallback_refresh_token,
        expires_in=int(str(payload["expires_in"])),
    )


async def exchange_code_for_tokens(code: str) -> TokenResponse:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        payload = response.json()

    return _parse_token_response(payload, fallback_refresh_token=None)


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        payload = response.json()

    return _parse_token_response(payload, fallback_refresh_token=refresh_token)
