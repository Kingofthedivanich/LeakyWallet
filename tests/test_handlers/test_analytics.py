import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.analytics import open_analytics
from LeakyWallet.bot.handlers.subscriptions import open_subscription_card
from LeakyWallet.bot.keyboards import MENU_ANALYTICS, SUBS_CARD_PREFIX
from LeakyWallet.db.models.service import ServiceCategory
from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository

_NEXT_CHARGE = datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC)


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


async def test_open_analytics_does_not_raise_for_empty_and_populated_accounts(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=970401, is_bot=False, first_name="Test")
    chat = Chat(id=970401, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    message = _fake_message(bot, tg_user, chat, "/dummy")
    empty_callback = _fake_callback(bot, tg_user, message, MENU_ANALYTICS)
    await open_analytics(empty_callback, session, user)  # must not raise on empty account

    subscriptions = SubscriptionRepository(session)
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
        next_charge_at=_NEXT_CHARGE,
    )

    populated_callback = _fake_callback(bot, tg_user, message, MENU_ANALYTICS)
    await open_analytics(populated_callback, session, user)


async def test_subscription_card_shows_cancel_button_for_catalog_service(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=970402, is_bot=False, first_name="Test")
    chat = Chat(id=970402, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    services = ServiceRepository(session)
    service = await services.create(
        slug="test-cancelable",
        name="Test Cancelable",
        domain_patterns=["cancelable.example"],
        cancel_url="https://cancelable.example/cancel",
        category=ServiceCategory.OTHER,
    )

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        service_id=service.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Test Cancelable",
    )

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, f"{SUBS_CARD_PREFIX}{subscription.id}")

    await open_subscription_card(callback, session, user)  # must not raise
