import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.subscriptions import (
    ask_delete_confirmation,
    confirm_delete,
    open_subscription_card,
    open_subscriptions_list,
)
from LeakyWallet.bot.keyboards import (
    MENU_SUBSCRIPTIONS,
    SUBS_CARD_PREFIX,
    SUBS_DELETE_CONFIRM_PREFIX,
    SUBS_DELETE_PREFIX,
)
from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionStatus
from LeakyWallet.db.models.user import User
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.subscriptions import SubscriptionService

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


async def _make_user(session: AsyncSession, tg_id: int) -> User:
    users = UserRepository(session)
    return await users.create(tg_id=tg_id, timezone="UTC", base_currency="USD")


async def test_open_list_does_not_raise_for_empty_and_populated_lists(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=555101, is_bot=False, first_name="Test")
    chat = Chat(id=555101, type="private")
    user = await _make_user(session, tg_user.id)
    message = _fake_message(bot, tg_user, chat, "/dummy")

    empty_callback = _fake_callback(bot, tg_user, message, MENU_SUBSCRIPTIONS)
    await open_subscriptions_list(empty_callback, session, user)

    service = SubscriptionService(SubscriptionRepository(session))
    await service.create(
        user_id=user.id,
        custom_name="Netflix",
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )

    populated_callback = _fake_callback(bot, tg_user, message, MENU_SUBSCRIPTIONS)
    await open_subscriptions_list(populated_callback, session, user)


async def test_card_and_delete_flow(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=555102, is_bot=False, first_name="Test")
    chat = Chat(id=555102, type="private")
    user = await _make_user(session, tg_user.id)

    service = SubscriptionService(SubscriptionRepository(session))
    subscription = await service.create(
        user_id=user.id,
        custom_name="Spotify",
        amount=Decimal("5.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )

    message = _fake_message(bot, tg_user, chat, "/dummy")

    card_callback = _fake_callback(bot, tg_user, message, f"{SUBS_CARD_PREFIX}{subscription.id}")
    await open_subscription_card(card_callback, session, user)

    delete_callback = _fake_callback(
        bot, tg_user, message, f"{SUBS_DELETE_PREFIX}{subscription.id}"
    )
    await ask_delete_confirmation(delete_callback, session, user)

    confirm_callback = _fake_callback(
        bot, tg_user, message, f"{SUBS_DELETE_CONFIRM_PREFIX}{subscription.id}"
    )
    await confirm_delete(confirm_callback, session, user)

    refreshed = await service.get_owned(subscription.id, user.id)
    assert refreshed is not None
    assert refreshed.status == SubscriptionStatus.CANCELLED
    assert subscription.id not in {s.id for s in await service.list_visible(user.id)}


async def test_card_not_found_for_other_users_subscription(session: AsyncSession, bot: Bot) -> None:
    owner = await _make_user(session, 555201)
    intruder = TgUser(id=555202, is_bot=False, first_name="Intruder")
    intruder_user = await _make_user(session, intruder.id)

    service = SubscriptionService(SubscriptionRepository(session))
    subscription = await service.create(
        user_id=owner.id,
        custom_name="Private",
        amount=Decimal("1.00"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )

    chat = Chat(id=intruder.id, type="private")
    message = _fake_message(bot, intruder, chat, "/dummy")
    card_callback = _fake_callback(bot, intruder, message, f"{SUBS_CARD_PREFIX}{subscription.id}")

    await open_subscription_card(card_callback, session, intruder_user)
