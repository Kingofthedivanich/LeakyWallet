import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.subscription import Subscription
from LeakyWallet.db.models.transaction import Transaction
from LeakyWallet.mail.oauth import TokenResponse
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService
from LeakyWallet.workers.parse import parse_candidate
from tests.helpers import SessionFactory


async def _make_email_account(session: AsyncSession, tg_id: int) -> tuple[int, int]:
    users = UserRepository(session)
    user = await users.create(tg_id=tg_id, timezone="UTC", base_currency="RUB")
    email_service = EmailAccountService(EmailAccountRepository(session))
    account = await email_service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )
    return user.id, account.id


async def test_parse_candidate_creates_transaction_from_recognizable_receipt(
    session: AsyncSession,
) -> None:
    user_id, email_account_id = await _make_email_account(session, 980001)
    ctx: dict[str, Any] = {"session_factory": SessionFactory(session)}

    await parse_candidate(
        ctx,
        email_account_id,
        "msg-parse-1",
        "Netflix <billing@netflix.com>",
        "Ваш чек Netflix",
        "Списано 799,00 ₽ за ежемесячную подписку Netflix.",
        datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC).isoformat(),
    )

    result = await session.execute(
        select(Transaction).where(Transaction.email_account_id == email_account_id)
    )
    transactions = result.scalars().all()
    assert len(transactions) == 1
    assert transactions[0].amount == Decimal("799.00")

    result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscriptions = result.scalars().all()
    assert len(subscriptions) == 1
    assert subscriptions[0].custom_name == "Netflix"


async def test_parse_candidate_rerun_does_not_duplicate(session: AsyncSession) -> None:
    _, email_account_id = await _make_email_account(session, 980002)
    ctx: dict[str, Any] = {"session_factory": SessionFactory(session)}

    args = (
        email_account_id,
        "msg-parse-2",
        "Netflix <billing@netflix.com>",
        "Ваш чек Netflix",
        "Списано 799,00 ₽ за ежемесячную подписку Netflix.",
        datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC).isoformat(),
    )

    await parse_candidate(ctx, *args)
    await parse_candidate(ctx, *args)  # simulate the job being enqueued/run twice

    result = await session.execute(
        select(Transaction).where(Transaction.email_account_id == email_account_id)
    )
    assert len(result.scalars().all()) == 1


async def test_parse_candidate_ignores_unparseable_message(session: AsyncSession) -> None:
    _, email_account_id = await _make_email_account(session, 980003)
    ctx: dict[str, Any] = {"session_factory": SessionFactory(session)}

    await parse_candidate(
        ctx,
        email_account_id,
        "msg-parse-3",
        "Netflix <news@netflix.com>",
        "New shows added this week",
        "Check out the latest movies and shows now streaming.",
        datetime.datetime(2026, 8, 5, tzinfo=datetime.UTC).isoformat(),
    )

    result = await session.execute(
        select(Transaction).where(Transaction.email_account_id == email_account_id)
    )
    assert result.scalars().all() == []


async def test_parse_candidate_skips_unknown_email_account(session: AsyncSession) -> None:
    ctx: dict[str, Any] = {"session_factory": SessionFactory(session)}
    await parse_candidate(
        ctx,
        9_999_999,
        "msg-parse-4",
        "Netflix <billing@netflix.com>",
        "Receipt",
        "Charged $9.99",
        datetime.datetime.now(datetime.UTC).isoformat(),
    )  # must not raise
