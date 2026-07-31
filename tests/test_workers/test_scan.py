import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

import LeakyWallet.workers.scan as scan_module
from LeakyWallet.db.models.email_account import EmailAccountStatus
from LeakyWallet.mail.base import RawMessage
from LeakyWallet.mail.oauth import TokenResponse
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService
from tests.helpers import SessionFactory


class _FakeArqRedis:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[Any, ...]]] = []

    async def enqueue_job(self, name: str, *args: Any) -> None:
        self.enqueued.append((name, args))


class _FakeGmailClient:
    def __init__(
        self, access_token: str, *, catalog_domains: Any, keywords: Any, on_progress: Any = None
    ) -> None:
        self.on_progress = on_progress

    async def fetch_since(self, cursor: str | None) -> tuple[list[RawMessage], str]:
        if self.on_progress is not None:
            await self.on_progress(1, 2)
            await self.on_progress(2, 2)
        message = RawMessage(
            message_id="m1",
            sender="billing@netflix.com",
            subject="Receipt",
            snippet="snippet",
            received_at=datetime.datetime.now(datetime.UTC),
        )
        return [message], "new-cursor-1"


class _FailingGmailClient:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def fetch_since(self, cursor: str | None) -> tuple[list[RawMessage], str]:
        raise RuntimeError("boom")


async def _connected_account(session: AsyncSession, tg_id: int) -> Any:
    users = UserRepository(session)
    user = await users.create(tg_id=tg_id, timezone="UTC", base_currency="USD")
    service = EmailAccountService(EmailAccountRepository(session))
    return await service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )


async def test_scan_email_account_bootstrap_enqueues_candidates_and_reports_progress(
    session: AsyncSession, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = await _connected_account(session, 950001)
    assert account.cursor is None  # bootstrap: no cursor yet

    monkeypatch.setattr(scan_module, "GmailClient", _FakeGmailClient)

    send_mock = AsyncMock(return_value=None)
    bot.send_message = send_mock

    fake_redis = _FakeArqRedis()
    ctx: dict[str, Any] = {
        "session_factory": SessionFactory(session),
        "bot": bot,
        "redis": fake_redis,
    }

    await scan_module.scan_email_account(ctx, account.id)

    assert account.cursor == "new-cursor-1"
    assert account.last_synced_at is not None
    assert [job for job, _ in fake_redis.enqueued] == ["parse_candidate"]
    job_name, job_args = fake_redis.enqueued[0]
    assert job_args[0] == account.id
    assert job_args[1] == "m1"
    # started + at least one progress update + done
    assert send_mock.await_count >= 2


async def test_scan_email_account_incremental_does_not_send_started_message(
    session: AsyncSession, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = await _connected_account(session, 950002)
    account.cursor = "existing-cursor"
    await session.flush()

    monkeypatch.setattr(scan_module, "GmailClient", _FakeGmailClient)

    send_mock = AsyncMock(return_value=None)
    bot.send_message = send_mock

    ctx: dict[str, Any] = {
        "session_factory": SessionFactory(session),
        "bot": bot,
        "redis": _FakeArqRedis(),
    }

    await scan_module.scan_email_account(ctx, account.id)

    sent_texts = [call.args[1] for call in send_mock.await_args_list]
    assert scan_module.texts.SCAN_STARTED not in sent_texts


async def test_scan_email_account_marks_error_on_fetch_failure(
    session: AsyncSession, bot: Bot, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = await _connected_account(session, 950003)

    monkeypatch.setattr(scan_module, "GmailClient", _FailingGmailClient)

    send_mock = AsyncMock(return_value=None)
    bot.send_message = send_mock

    ctx: dict[str, Any] = {
        "session_factory": SessionFactory(session),
        "bot": bot,
        "redis": _FakeArqRedis(),
    }

    await scan_module.scan_email_account(ctx, account.id)

    assert account.status == EmailAccountStatus.ERROR


async def test_scan_email_account_skips_unknown_account(session: AsyncSession) -> None:
    ctx: dict[str, Any] = {"session_factory": SessionFactory(session), "redis": _FakeArqRedis()}
    await scan_module.scan_email_account(ctx, 9_999_999)  # must not raise


async def test_scan_all_email_accounts_enqueues_each_active_account(
    session: AsyncSession,
) -> None:
    account = await _connected_account(session, 950004)

    fake_redis = _FakeArqRedis()
    ctx: dict[str, Any] = {"session_factory": SessionFactory(session), "redis": fake_redis}

    await scan_module.scan_all_email_accounts(ctx)

    assert ("scan_email_account", (account.id,)) in fake_redis.enqueued
