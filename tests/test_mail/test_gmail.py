import asyncio
import datetime
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from LeakyWallet.mail.base import RawMessage
from LeakyWallet.mail.gmail import (
    GMAIL_HISTORY_LIST_URL,
    GMAIL_MESSAGE_GET_URL,
    GMAIL_MESSAGES_LIST_URL,
    GMAIL_PROFILE_URL,
    GmailClient,
    _build_bootstrap_query,
    _request_with_backoff,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=MagicMock(), response=self)  # type: ignore[arg-type]

    def json(self) -> dict[str, Any]:
        return self._payload


def _message_payload(
    message_id: str, sender: str, subject: str, snippet: str, internal_date_ms: int
) -> dict[str, Any]:
    return {
        "id": message_id,
        "snippet": snippet,
        "internalDate": str(internal_date_ms),
        "payload": {
            "headers": [
                {"name": "From", "value": sender},
                {"name": "Subject", "value": subject},
            ]
        },
    }


def test_build_bootstrap_query_includes_senders_and_keywords() -> None:
    query = _build_bootstrap_query(["netflix.com"], ["invoice"])
    assert query.startswith("after:")
    assert "from:netflix.com" in query
    assert "subject:invoice" in query


def test_is_relevant_matches_by_keyword_when_sender_unknown() -> None:
    client = GmailClient("token", catalog_domains=["netflix.com"], keywords=["invoice"])
    message = RawMessage(
        message_id="x",
        sender="billing@some-random-service.com",
        subject="Your invoice is ready",
        snippet="",
        received_at=datetime.datetime.now(datetime.UTC),
    )
    assert client._is_relevant(message) is True


def test_is_relevant_rejects_unmatched_message() -> None:
    client = GmailClient("token", catalog_domains=["netflix.com"], keywords=["invoice"])
    message = RawMessage(
        message_id="x",
        sender="friend@example.com",
        subject="Lunch tomorrow?",
        snippet="",
        received_at=datetime.datetime.now(datetime.UTC),
    )
    assert client._is_relevant(message) is False


async def test_request_with_backoff_retries_on_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [_FakeResponse(429), _FakeResponse(200, {"ok": True})]

    async def fake_request(
        self: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> _FakeResponse:
        return responses.pop(0)

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async with httpx.AsyncClient() as client:
        response = await _request_with_backoff(client, "GET", "https://example.com")

    assert response.status_code == 200
    assert len(sleeps) == 1


async def test_bootstrap_scan_paginates_and_filters_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_request(
        self: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> _FakeResponse:
        calls.append(url)
        if url == GMAIL_MESSAGES_LIST_URL:
            if kwargs["params"].get("pageToken") is None:
                return _FakeResponse(200, {"messages": [{"id": "m1"}], "nextPageToken": "page2"})
            return _FakeResponse(200, {"messages": [{"id": "m2"}]})
        if url == GMAIL_MESSAGE_GET_URL.format(id="m1"):
            return _FakeResponse(
                200,
                _message_payload(
                    "m1", "billing@netflix.com", "Your receipt", "snippet", 1_700_000_000_000
                ),
            )
        if url == GMAIL_MESSAGE_GET_URL.format(id="m2"):
            return _FakeResponse(
                200,
                _message_payload(
                    "m2", "noreply@unrelated.com", "hello", "snippet", 1_700_000_000_000
                ),
            )
        if url == GMAIL_PROFILE_URL:
            return _FakeResponse(200, {"emailAddress": "me@gmail.com", "historyId": "999"})
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GmailClient("token", catalog_domains=["netflix.com"], keywords=["invoice"])
    messages, cursor = await client.fetch_since(None)

    assert cursor == "999"
    assert [message.message_id for message in messages] == ["m1"]
    assert calls.count(GMAIL_MESSAGES_LIST_URL) == 2  # followed pagination


async def test_incremental_scan_returns_only_new_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request(
        self: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> _FakeResponse:
        if url == GMAIL_HISTORY_LIST_URL:
            assert kwargs["params"]["startHistoryId"] == "500"
            return _FakeResponse(
                200,
                {
                    "history": [{"messagesAdded": [{"message": {"id": "m3"}}]}],
                    "historyId": "1001",
                },
            )
        if url == GMAIL_MESSAGE_GET_URL.format(id="m3"):
            return _FakeResponse(
                200,
                _message_payload(
                    "m3", "billing@spotify.com", "Payment", "snippet", 1_700_000_000_000
                ),
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GmailClient("token", catalog_domains=["spotify.com"], keywords=[])
    messages, cursor = await client.fetch_since("500")

    assert cursor == "1001"
    assert [message.message_id for message in messages] == ["m3"]


async def test_incremental_scan_falls_back_to_bootstrap_when_history_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request(
        self: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> _FakeResponse:
        if url == GMAIL_HISTORY_LIST_URL:
            return _FakeResponse(404)
        if url == GMAIL_MESSAGES_LIST_URL:
            return _FakeResponse(200, {"messages": []})
        if url == GMAIL_PROFILE_URL:
            return _FakeResponse(200, {"historyId": "2000"})
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GmailClient("token", catalog_domains=[], keywords=[])
    messages, cursor = await client.fetch_since("stale-cursor")

    assert messages == []
    assert cursor == "2000"


async def test_fetch_since_reports_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_request(
        self: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> _FakeResponse:
        if url == GMAIL_MESSAGES_LIST_URL:
            return _FakeResponse(200, {"messages": [{"id": "m1"}, {"id": "m2"}]})
        if url == GMAIL_PROFILE_URL:
            return _FakeResponse(200, {"historyId": "1"})
        message_id = url.rsplit("/", 1)[-1]
        return _FakeResponse(
            200,
            _message_payload(
                message_id, "billing@netflix.com", "Receipt", "snippet", 1_700_000_000_000
            ),
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    progress_calls: list[tuple[int, int]] = []

    async def on_progress(done: int, total: int) -> None:
        progress_calls.append((done, total))

    client = GmailClient(
        "token", catalog_domains=["netflix.com"], keywords=[], on_progress=on_progress
    )
    await client.fetch_since(None)

    assert progress_calls == [(2, 2)]
