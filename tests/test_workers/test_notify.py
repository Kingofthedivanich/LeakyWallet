import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.db.models.user import ReminderPolicy
from LeakyWallet.repositories.reminders import ReminderRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.workers.notify import recompute_reminders, send_due_reminders


class _SessionFactory:
    """Wraps the test's transactional session so worker jobs reuse it instead of
    opening a real connection - keeps the test isolated via the session fixture's
    outer rollback."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> "_SessionFactory":
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> None:
        return None


async def test_recompute_then_send_due_days_before_reminder(
    session: AsyncSession, bot: Bot
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=810001, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.DAYS_BEFORE

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
        next_charge_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=10),
    )

    ctx: dict[str, Any] = {"session_factory": _SessionFactory(session), "bot": bot}
    await recompute_reminders(ctx)

    reminder_repo = ReminderRepository(session)
    reminder = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=subscription.id, kind=ReminderPolicy.DAYS_BEFORE
    )
    assert reminder is not None

    # Force it due right now, regardless of the real fire_at computed above.
    reminder.fire_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)
    await session.flush()

    send_mock = AsyncMock(return_value=None)
    bot.send_message = send_mock

    await send_due_reminders(ctx)

    send_mock.assert_awaited_once()
    assert send_mock.await_args is not None
    assert send_mock.await_args.args[0] == user.tg_id

    refreshed = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=subscription.id, kind=ReminderPolicy.DAYS_BEFORE
    )
    assert refreshed is None  # sent_at is now set, so it's no longer "pending"

    # A second pass must not send it again.
    await send_due_reminders(ctx)
    assert send_mock.await_count == 1


async def test_send_due_weekly_digest_reminder(session: AsyncSession, bot: Bot) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=810002, timezone="UTC", base_currency="USD")

    reminder_repo = ReminderRepository(session)
    await reminder_repo.upsert_pending(
        user_id=user.id,
        subscription_id=None,
        kind=ReminderPolicy.WEEKLY_DIGEST,
        fire_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1),
    )

    send_mock = AsyncMock(return_value=None)
    bot.send_message = send_mock

    ctx: dict[str, Any] = {"session_factory": _SessionFactory(session), "bot": bot}
    await send_due_reminders(ctx)

    send_mock.assert_awaited_once()
    refreshed = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=None, kind=ReminderPolicy.WEEKLY_DIGEST
    )
    assert refreshed is None


async def test_send_due_reminders_without_bot_is_a_noop(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=810003, timezone="UTC", base_currency="USD")

    reminder_repo = ReminderRepository(session)
    await reminder_repo.upsert_pending(
        user_id=user.id,
        subscription_id=None,
        kind=ReminderPolicy.WEEKLY_DIGEST,
        fire_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1),
    )

    ctx: dict[str, Any] = {"session_factory": _SessionFactory(session), "bot": None}
    await send_due_reminders(ctx)

    still_pending = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=None, kind=ReminderPolicy.WEEKLY_DIGEST
    )
    assert still_pending is not None
