import datetime
import uuid
from decimal import Decimal
from typing import Any

import httpx
import pytest

from LeakyWallet.config import get_settings
from LeakyWallet.mail.base import RawMessage
from LeakyWallet.parsing.llm import extract_with_llm
from LeakyWallet.parsing.pipeline import parse_message


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": self._content}}]}


def _configure_openrouter(monkeypatch: pytest.MonkeyPatch, *, daily_limit: int = 20) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_daily_limit_per_user", daily_limit)


def _unique_text(label: str) -> str:
    return f"{label} {uuid.uuid4()}"


async def test_extract_with_llm_is_noop_when_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_post(*args: Any, **kwargs: Any) -> _FakeResponse:
        raise AssertionError("must not call the network when openrouter_api_key is empty")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_post)

    result = await extract_with_llm(_unique_text("unconfigured"), user_id=1)
    assert result is None


async def test_extract_with_llm_recognizes_unknown_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        return _FakeResponse(
            '{"is_charge": true, "amount": 349.5, "currency": "usd", "period": "yearly"}'
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await extract_with_llm(
        _unique_text("Some Obscure SaaS charged your card"), user_id=101
    )

    assert result is not None
    assert result.is_charge is True
    assert result.amount == Decimal("349.5")
    assert result.currency == "usd"
    assert result.period.value == "yearly"


async def test_extract_with_llm_handles_code_fenced_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse('```json\n{"is_charge": false}\n```')

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await extract_with_llm(_unique_text("fenced"), user_id=102)
    assert result is not None
    assert result.is_charge is False


async def test_extract_with_llm_returns_none_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse("this is not json at all")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await extract_with_llm(_unique_text("garbage"), user_id=103)
    assert result is None  # must not raise - unparsed, not a crash


async def test_extract_with_llm_returns_none_on_schema_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse('{"is_charge": "maybe", "amount": "a lot"}')

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = await extract_with_llm(_unique_text("schema-mismatch"), user_id=104)
    assert result is None


async def test_extract_with_llm_caches_by_normalized_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)
    calls = 0

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        nonlocal calls
        calls += 1
        return _FakeResponse('{"is_charge": true, "amount": 9.99, "currency": "USD"}')

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    text = _unique_text("cache-me")
    first = await extract_with_llm(text, user_id=105)
    second = await extract_with_llm(text.upper() + "  ", user_id=105)  # same after normalization

    assert calls == 1
    assert first == second


async def test_extract_with_llm_stops_calling_after_daily_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch, daily_limit=1)
    calls = 0

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        nonlocal calls
        calls += 1
        return _FakeResponse('{"is_charge": true, "amount": 1.00, "currency": "USD"}')

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    user_id = 999_000 + uuid.uuid4().int % 1000
    first = await extract_with_llm(_unique_text("limit-a"), user_id=user_id)
    second = await extract_with_llm(_unique_text("limit-b"), user_id=user_id)

    assert first is not None
    assert second is None
    assert calls == 1


async def test_pipeline_recognizes_unrecognized_wording_via_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(
            '{"is_charge": true, "amount": 12.50, "currency": "usd", "period": "monthly"}'
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    message = RawMessage(
        message_id=_unique_text("pipeline-llm"),
        sender="Some Obscure SaaS <billing@obscure-saas.example>",
        subject="Payment confirmation",
        snippet=_unique_text(
            "Your card was charged twelve dollars fifty cents for your recurring plan."
        ),
        received_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
    )

    receipt = await parse_message(message, user_id=106)

    assert receipt is not None
    assert receipt.amount == Decimal("12.50")
    assert receipt.currency == "USD"
    assert receipt.period.value == "monthly"
    assert receipt.service_slug is None
    assert receipt.sender_name == "Some Obscure SaaS"


async def test_pipeline_invalid_llm_response_yields_no_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_openrouter(monkeypatch)

    async def fake_post(self: httpx.AsyncClient, url: str, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse("not json")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    message = RawMessage(
        message_id=_unique_text("pipeline-llm-bad"),
        sender="Some Obscure SaaS <billing@obscure-saas.example>",
        subject="Payment confirmation",
        snippet=_unique_text(
            "Your card was charged twelve dollars fifty cents for your recurring plan."
        ),
        received_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
    )

    receipt = await parse_message(message, user_id=107)  # must not raise
    assert receipt is None
