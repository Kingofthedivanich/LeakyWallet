import datetime

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.email_connect import disconnect_email, open_email_settings
from LeakyWallet.bot.keyboards import EMAIL_DISCONNECT, SETTINGS_EMAIL
from LeakyWallet.db.models.email_account import EmailProvider
from LeakyWallet.mail.oauth import TokenResponse
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService


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


async def test_open_email_settings_without_config_does_not_crash(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=900201, is_bot=False, first_name="Test")
    chat = Chat(id=900201, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, SETTINGS_EMAIL)

    # GOOGLE_CLIENT_ID is empty in the test environment - exercises the
    # "not configured" branch instead of generating a broken auth URL.
    await open_email_settings(callback, session, user)


async def test_open_email_settings_shows_connected_status(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=900202, is_bot=False, first_name="Test")
    chat = Chat(id=900202, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    service = EmailAccountService(EmailAccountRepository(session))
    await service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, SETTINGS_EMAIL)

    await open_email_settings(callback, session, user)


async def test_disconnect_email_removes_account(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=900203, is_bot=False, first_name="Test")
    chat = Chat(id=900203, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    repository = EmailAccountRepository(session)
    service = EmailAccountService(repository)
    await service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, EMAIL_DISCONNECT)

    await disconnect_email(callback, session, user)

    assert await repository.get_by_user_and_provider(user.id, EmailProvider.GMAIL) is None
