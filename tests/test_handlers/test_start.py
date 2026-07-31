import datetime

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.start import cmd_start, on_currency_chosen, on_timezone_chosen
from LeakyWallet.bot.keyboards import ONBOARDING_CURRENCY_PREFIX, ONBOARDING_TIMEZONE_PREFIX
from LeakyWallet.bot.states import OnboardingStates
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
        id="1",
        from_user=tg_user,
        chat_instance="1",
        message=message,
        data=data,
    )
    return callback.as_(bot)


async def test_cmd_start_creates_state_and_greets_user(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=111111, is_bot=False, first_name="Test")
    chat = Chat(id=111111, type="private")

    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    message = _fake_message(bot, tg_user, chat, "/start")
    state = _fsm_context(bot, chat.id, tg_user.id)

    await cmd_start(message, state, user)

    assert await state.get_state() == OnboardingStates.choosing_timezone.state


async def test_onboarding_flow_updates_user_and_shows_menu(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=222222, is_bot=False, first_name="Test")
    chat = Chat(id=222222, type="private")

    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    message = _fake_message(bot, tg_user, chat, "/start")
    state = _fsm_context(bot, chat.id, tg_user.id)
    await cmd_start(message, state, user)

    timezone_callback = _fake_callback(
        bot, tg_user, message, f"{ONBOARDING_TIMEZONE_PREFIX}Europe/Moscow"
    )
    await on_timezone_chosen(timezone_callback, state)

    assert await state.get_state() == OnboardingStates.choosing_currency.state
    assert (await state.get_data())["timezone"] == "Europe/Moscow"

    currency_callback = _fake_callback(bot, tg_user, message, f"{ONBOARDING_CURRENCY_PREFIX}RUB")
    await on_currency_chosen(currency_callback, state, session, user)

    assert await state.get_state() is None
    assert user.timezone == "Europe/Moscow"
    assert user.base_currency == "RUB"
