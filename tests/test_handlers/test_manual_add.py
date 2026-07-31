import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.manual_add import (
    on_amount_entered,
    on_currency_chosen,
    on_date_entered,
    on_name_entered,
    on_period_chosen,
    start_add_subscription,
)
from LeakyWallet.bot.keyboards import ADD_CURRENCY_PREFIX, ADD_PERIOD_PREFIX, SUBS_ADD
from LeakyWallet.bot.states import AddSubscriptionStates
from LeakyWallet.db.models.subscription import Subscription
from LeakyWallet.repositories.users import UserRepository


def _fsm_context(bot: Bot, chat_id: int, user_id: int) -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=bot.id, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


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


async def test_full_add_subscription_flow_creates_subscription(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=555001, is_bot=False, first_name="Test")
    chat = Chat(id=555001, type="private")

    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="Europe/Moscow", base_currency="RUB")

    message = _fake_message(bot, tg_user, chat, "/dummy")
    state = _fsm_context(bot, chat.id, tg_user.id)

    add_callback = _fake_callback(bot, tg_user, message, SUBS_ADD)
    await start_add_subscription(add_callback, state)
    assert await state.get_state() == AddSubscriptionStates.entering_name.state

    name_message = _fake_message(bot, tg_user, chat, "Netflix")
    await on_name_entered(name_message, state)
    assert await state.get_state() == AddSubscriptionStates.entering_amount.state

    amount_message = _fake_message(bot, tg_user, chat, "299.90")
    await on_amount_entered(amount_message, state)
    assert await state.get_state() == AddSubscriptionStates.choosing_currency.state

    currency_callback = _fake_callback(bot, tg_user, message, f"{ADD_CURRENCY_PREFIX}RUB")
    await on_currency_chosen(currency_callback, state)
    assert await state.get_state() == AddSubscriptionStates.choosing_period.state

    period_callback = _fake_callback(bot, tg_user, message, f"{ADD_PERIOD_PREFIX}monthly")
    await on_period_chosen(period_callback, state)
    assert await state.get_state() == AddSubscriptionStates.entering_next_charge_at.state

    date_message = _fake_message(bot, tg_user, chat, "15.08.2026")
    await on_date_entered(date_message, state, session, user)

    assert await state.get_state() is None

    result = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscriptions = result.scalars().all()
    assert len(subscriptions) == 1
    subscription = subscriptions[0]
    assert subscription.custom_name == "Netflix"
    assert subscription.amount == Decimal("299.90")
    assert subscription.currency == "RUB"
    assert subscription.next_charge_at is not None


async def test_invalid_amount_reprompts_without_advancing_state(bot: Bot) -> None:
    tg_user = TgUser(id=555002, is_bot=False, first_name="Test")
    chat = Chat(id=555002, type="private")
    state = _fsm_context(bot, chat.id, tg_user.id)
    await state.set_state(AddSubscriptionStates.entering_amount)

    message = _fake_message(bot, tg_user, chat, "not a number")
    await on_amount_entered(message, state)

    assert await state.get_state() == AddSubscriptionStates.entering_amount.state
