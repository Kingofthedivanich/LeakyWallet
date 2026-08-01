import datetime
from decimal import Decimal

from aiogram import Bot
from aiogram.types import CallbackQuery, Chat, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.handlers.privacy import cancel_wipe, confirm_wipe, export_csv
from LeakyWallet.bot.keyboards import PRIVACY_EXPORT, PRIVACY_WIPE_CANCEL, PRIVACY_WIPE_CONFIRM
from LeakyWallet.db.models.email_account import EmailAccount
from LeakyWallet.db.models.reminder import Reminder
from LeakyWallet.db.models.subscription import Subscription, SubscriptionPeriod, SubscriptionSource
from LeakyWallet.db.models.transaction import Transaction
from LeakyWallet.db.models.user import ReminderPolicy, User
from LeakyWallet.mail.oauth import TokenResponse
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.reminders import ReminderRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
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


async def _make_full_user(session: AsyncSession, tg_id: int) -> tuple[User, int, int, int, int]:
    users = UserRepository(session)
    user = await users.create(tg_id=tg_id, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.WEEKLY_DIGEST

    email_service = EmailAccountService(EmailAccountRepository(session))
    email_account = await email_service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Spotify",
    )

    transactions = TransactionRepository(session)
    transaction = await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
        email_account_id=email_account.id,
        message_id="msg-wipe-1",
    )

    reminders = ReminderRepository(session)
    reminder = await reminders.upsert_pending(
        user_id=user.id,
        subscription_id=None,
        kind=ReminderPolicy.WEEKLY_DIGEST,
        fire_at=datetime.datetime(2026, 7, 6, tzinfo=datetime.UTC),
    )

    await session.flush()
    return user, email_account.id, subscription.id, transaction.id, reminder.id


async def test_wipe_confirm_deletes_all_user_data(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=970301, is_bot=False, first_name="Test")
    chat = Chat(id=970301, type="private")
    user, email_account_id, subscription_id, transaction_id, reminder_id = await _make_full_user(
        session, tg_user.id
    )
    user_id = user.id

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, PRIVACY_WIPE_CONFIRM)

    await confirm_wipe(callback, session, user)
    await session.flush()  # session.get() reads the identity map before autoflush would fire

    assert await UserRepository(session).get_by_id(user_id) is None
    assert await session.get(EmailAccount, email_account_id) is None
    assert await session.get(Subscription, subscription_id) is None
    assert await session.get(Transaction, transaction_id) is None
    assert await session.get(Reminder, reminder_id) is None


async def test_cancel_wipe_keeps_data(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=970302, is_bot=False, first_name="Test")
    chat = Chat(id=970302, type="private")
    user, *_ = await _make_full_user(session, tg_user.id)
    user_id = user.id

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, PRIVACY_WIPE_CANCEL)

    await cancel_wipe(callback)

    assert await UserRepository(session).get_by_id(user_id) is not None


async def test_export_csv_sends_document_when_transactions_exist(
    session: AsyncSession, bot: Bot
) -> None:
    tg_user = TgUser(id=970303, is_bot=False, first_name="Test")
    chat = Chat(id=970303, type="private")
    user, *_ = await _make_full_user(session, tg_user.id)

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, PRIVACY_EXPORT)

    await export_csv(callback, session, user)  # must not raise


async def test_export_csv_alerts_when_no_transactions(session: AsyncSession, bot: Bot) -> None:
    tg_user = TgUser(id=970304, is_bot=False, first_name="Test")
    chat = Chat(id=970304, type="private")
    users = UserRepository(session)
    user = await users.create(tg_id=tg_user.id, timezone="UTC", base_currency="USD")

    message = _fake_message(bot, tg_user, chat, "/dummy")
    callback = _fake_callback(bot, tg_user, message, PRIVACY_EXPORT)

    await export_csv(callback, session, user)  # must not raise
