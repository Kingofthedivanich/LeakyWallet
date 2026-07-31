import urllib.parse
from typing import Any

import httpx
import pytest

from LeakyWallet.mail.oauth import (
    GMAIL_READONLY_SCOPE,
    create_auth_url,
    exchange_code_for_tokens,
    pop_user_id_for_state,
    refresh_access_token,
)


def _query(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


async def test_create_auth_url_contains_expected_params() -> None:
    url = await create_auth_url(user_id=42)
    query = _query(url)

    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query["scope"] == [GMAIL_READONLY_SCOPE]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    assert query["response_type"] == ["code"]
    assert "state" in query


async def test_state_round_trip_is_single_use() -> None:
    url = await create_auth_url(user_id=777)
    state = _query(url)["state"][0]

    assert await pop_user_id_for_state(state) == 777
    assert await pop_user_id_for_state(state) is None


async def test_pop_user_id_for_unknown_state_returns_none() -> None:
    assert await pop_user_id_for_state("does-not-exist") is None


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


async def test_exchange_code_for_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_post(self: httpx.AsyncClient, url: str, data: dict[str, Any]) -> _FakeResponse:
        assert url == "https://oauth2.googleapis.com/token"
        assert data["grant_type"] == "authorization_code"
        assert data["code"] == "some-code"
        return _FakeResponse(
            {"access_token": "access-123", "refresh_token": "refresh-456", "expires_in": 3599}
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    tokens = await exchange_code_for_tokens("some-code")

    assert tokens.access_token == "access-123"
    assert tokens.refresh_token == "refresh-456"
    assert tokens.expires_in == 3599


async def test_refresh_access_token_keeps_old_refresh_token_if_not_reissued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_post(self: httpx.AsyncClient, url: str, data: dict[str, Any]) -> _FakeResponse:
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "original-refresh-token"
        return _FakeResponse({"access_token": "new-access", "expires_in": 3600})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    tokens = await refresh_access_token("original-refresh-token")

    assert tokens.access_token == "new-access"
    assert tokens.refresh_token == "original-refresh-token"
