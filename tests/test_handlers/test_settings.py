import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.settings import set_currency, set_reminder_policy, set_timezone
from LeakyWallet.bot.keyboards import (
    SETTINGS_CURRENCY_PREFIX,
    SETTINGS_REMINDER_POLICY_PREFIX,
    SETTINGS_TIMEZONE_PREFIX,
)
from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.db.models.user import ReminderPolicy
from LeakyWallet.repositories.reminders import ReminderRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository


def _fake_message(bot: Bot, tg_user: TgUser, chat: Chat, text: str) -> Message:
    message = Message(
        message_id=1,
        date=datetime.datetime.now(datetime.UTC),
        chat=chat,
        from_user=tg_user,
        text=text,
    )
    return message.as_(bot)


def _fake_callback(bot: Bot, tg_user: TgUser, message: Message, data: str) -> CallbackQuery:
    callback = CallbackQuery(
        id="1", from_user=tg_user, chat_instance="1", message=message, data=data
    )
    return callback.as_(bot)


async def test_set_reminder_policy_triggers_recompute(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=820001, is_bot=False, first_name="Test")
    chat = Chat(id=820001, type="private")

    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

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

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(
        bot,
        tg_user,
        message,
        f"{SETTINGS_REMINDER_POLICY_PREFIX}{ReminderPolicy.DAYS_BEFORE.value}",
    )

    await set_reminder_policy(callback, session, user)

    assert user.reminder_policy == ReminderPolicy.DAYS_BEFORE

    reminder_repo = ReminderRepository(session)
    reminder = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=subscription.id, kind=ReminderPolicy.DAYS_BEFORE
    )
    assert reminder is not None


async def test_set_currency_updates_user(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=820002, is_bot=False, first_name="Test")
    chat = Chat(id=820002, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, f"{SETTINGS_CURRENCY_PREFIX}EUR")

    await set_currency(callback, user)

    assert user.base_currency == "EUR"


async def test_set_timezone_updates_user_and_recomputes_digest(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=820003, is_bot=False, first_name="Test")
    chat = Chat(id=820003, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.WEEKLY_DIGEST

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, f"{SETTINGS_TIMEZONE_PREFIX}Europe/Moscow")

    await set_timezone(callback, session, user)

    assert user.timezone == "Europe/Moscow"

    reminder_repo = ReminderRepository(session)
    reminder = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=None, kind=ReminderPolicy.WEEKLY_DIGEST
    )
    assert reminder is not None
