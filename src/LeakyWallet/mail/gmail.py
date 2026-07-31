import asyncio
import datetime
import random
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx

from LeakyWallet.mail.base import RawMessage

GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_MESSAGES_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_MESSAGE_GET_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{id}"
GMAIL_HISTORY_LIST_URL = "https://gmail.googleapis.com/gmail/v1/users/me/history"

BOOTSTRAP_LOOKBACK_DAYS = 365
FETCH_CONCURRENCY = 5
PROGRESS_BATCH_SIZE = 25

MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

SUBSCRIPTION_KEYWORDS: tuple[str, ...] = (
    "receipt",
    "invoice",
    "subscription",
    "payment",
    "charged",
    "renewed",
    "чек",
    "квитанция",
    "подписка",
    "оплата",
    "списание",
    "продлена",
    "платёж",
)


async def get_profile_email(access_token: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GMAIL_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        payload = response.json()
    return str(payload["emailAddress"])


async def _request_with_backoff(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    backoff = INITIAL_BACKOFF_SECONDS
    response: httpx.Response | None = None

    for attempt in range(MAX_RETRIES):
        response = await client.request(method, url, **kwargs)
        if response.status_code not in RETRYABLE_STATUS_CODES:
            return response
        if attempt == MAX_RETRIES - 1:
            return response
        await asyncio.sleep(backoff + random.uniform(0, backoff * 0.1))
        backoff *= 2

    assert response is not None
    return response


def _build_bootstrap_query(catalog_domains: Sequence[str], keywords: Sequence[str]) -> str:
    after_date = (
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=BOOTSTRAP_LOOKBACK_DAYS)
    ).strftime("%Y/%m/%d")
    sender_terms = [f"from:{domain}" for domain in catalog_domains]
    keyword_terms = [f"subject:{keyword}" for keyword in keywords]
    or_clause = " OR ".join(sender_terms + keyword_terms)
    return f"after:{after_date} ({or_clause})"


class GmailClient:
    def __init__(
        self,
        access_token: str,
        *,
        catalog_domains: Sequence[str],
        keywords: Sequence[str],
        on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> None:
        self._access_token = access_token
        self._catalog_domains = catalog_domains
        self._keywords = keywords
        self._on_progress = on_progress

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._access_token}"}

    def _is_relevant(self, message: RawMessage) -> bool:
        sender_lower = message.sender.lower()
        if any(domain.lower() in sender_lower for domain in self._catalog_domains):
            return True
        subject_lower = message.subject.lower()
        return any(keyword.lower() in subject_lower for keyword in self._keywords)

    async def fetch_since(self, cursor: str | None) -> tuple[list[RawMessage], str]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if cursor is not None:
                history_result = await self._list_history_message_ids(client, cursor)
                if history_result is not None:
                    message_ids, new_cursor = history_result
                    messages = await self._fetch_messages_metadata(client, message_ids)
                    relevant = [message for message in messages if self._is_relevant(message)]
                    return relevant, new_cursor
                # startHistoryId expired on Gmail's side - fall back to a fresh bootstrap.

            query = _build_bootstrap_query(self._catalog_domains, self._keywords)
            message_ids = await self._list_message_ids(client, query)
            messages = await self._fetch_messages_metadata(client, message_ids)
            relevant = [message for message in messages if self._is_relevant(message)]
            new_cursor = await self._current_history_id(client)
            return relevant, new_cursor

    async def _list_message_ids(self, client: httpx.AsyncClient, query: str) -> list[str]:
        ids: list[str] = []
        page_token: str | None = None

        while True:
            params: dict[str, str] = {"q": query, "maxResults": "100"}
            if page_token is not None:
                params["pageToken"] = page_token

            response = await _request_with_backoff(
                client, "GET", GMAIL_MESSAGES_LIST_URL, headers=self._headers(), params=params
            )
            response.raise_for_status()
            payload = response.json()
            ids.extend(message["id"] for message in payload.get("messages", []))

            page_token = payload.get("nextPageToken")
            if page_token is None:
                return ids

    async def _list_history_message_ids(
        self, client: httpx.AsyncClient, start_history_id: str
    ) -> tuple[list[str], str] | None:
        ids: list[str] = []
        page_token: str | None = None
        latest_history_id = start_history_id

        while True:
            params: dict[str, str] = {
                "startHistoryId": start_history_id,
                "historyTypes": "messageAdded",
                "maxResults": "500",
            }
            if page_token is not None:
                params["pageToken"] = page_token

            response = await _request_with_backoff(
                client, "GET", GMAIL_HISTORY_LIST_URL, headers=self._headers(), params=params
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()

            payload = response.json()
            for record in payload.get("history", []):
                for added in record.get("messagesAdded", []):
                    ids.append(added["message"]["id"])
            if "historyId" in payload:
                latest_history_id = payload["historyId"]

            page_token = payload.get("nextPageToken")
            if page_token is None:
                return ids, latest_history_id

    async def _fetch_message(self, client: httpx.AsyncClient, message_id: str) -> RawMessage:
        url = GMAIL_MESSAGE_GET_URL.format(id=message_id)
        response = await _request_with_backoff(
            client,
            "GET",
            url,
            headers=self._headers(),
            params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
        )
        response.raise_for_status()
        payload = response.json()

        headers = {
            header["name"]: header["value"]
            for header in payload.get("payload", {}).get("headers", [])
        }
        received_at = datetime.datetime.fromtimestamp(
            int(payload["internalDate"]) / 1000, tz=datetime.UTC
        )
        return RawMessage(
            message_id=payload["id"],
            sender=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            snippet=payload.get("snippet", ""),
            received_at=received_at,
        )

    async def _fetch_messages_metadata(
        self, client: httpx.AsyncClient, message_ids: Sequence[str]
    ) -> list[RawMessage]:
        semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

        async def fetch_one(message_id: str) -> RawMessage:
            async with semaphore:
                return await self._fetch_message(client, message_id)

        results: list[RawMessage] = []
        total = len(message_ids)

        for start in range(0, total, PROGRESS_BATCH_SIZE):
            chunk = message_ids[start : start + PROGRESS_BATCH_SIZE]
            chunk_results = await asyncio.gather(*(fetch_one(message_id) for message_id in chunk))
            results.extend(chunk_results)
            if self._on_progress is not None:
                await self._on_progress(len(results), total)

        return results

    async def _current_history_id(self, client: httpx.AsyncClient) -> str:
        response = await _request_with_backoff(
            client, "GET", GMAIL_PROFILE_URL, headers=self._headers()
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["historyId"])
