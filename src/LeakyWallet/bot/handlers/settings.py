import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.keyboards import (
    MENU_SETTINGS,
    SETTINGS_CURRENCY,
    SETTINGS_CURRENCY_PREFIX,
    SETTINGS_REMINDER_POLICY_PREFIX,
    SETTINGS_REMINDERS,
    SETTINGS_TIMEZONE,
    SETTINGS_TIMEZONE_PREFIX,
    currency_keyboard,
    reminder_policy_keyboard,
    settings_menu_keyboard,
    timezone_keyboard,
)
from LeakyWallet.db.models.user import ReminderPolicy, User
from LeakyWallet.repositories.reminders import ReminderRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.services.reminders import ReminderService
from LeakyWallet.services.subscriptions import SubscriptionService

router = Router(name="settings")


async def _recompute_reminders(session: AsyncSession, user: User) -> None:
    subscription_service = SubscriptionService(SubscriptionRepository(session))
    subscriptions = await subscription_service.list_visible(user.id)
    reminder_service = ReminderService(ReminderRepository(session))
    await reminder_service.recompute_for_user(
        user, subscriptions, datetime.datetime.now(datetime.UTC)
    )


@router.callback_query(F.data == MENU_SETTINGS)
async def open_settings_menu(callback: CallbackQuery, user: User) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.answer(
        texts.settings_overview(user), reply_markup=settings_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == SETTINGS_REMINDERS)
async def open_reminder_settings(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        texts.SETTINGS_REMINDERS_PROMPT, reply_markup=reminder_policy_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SETTINGS_REMINDER_POLICY_PREFIX))
async def set_reminder_policy(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    policy = ReminderPolicy(callback.data.removeprefix(SETTINGS_REMINDER_POLICY_PREFIX))
    user.reminder_policy = policy
    await _recompute_reminders(session, user)

    await callback.message.edit_text(
        f"{texts.SETTINGS_REMINDER_POLICY_SAVED}\n\n{texts.settings_overview(user)}",
        reply_markup=settings_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == SETTINGS_CURRENCY)
async def open_currency_settings(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        texts.SETTINGS_CURRENCY_PROMPT, reply_markup=currency_keyboard(SETTINGS_CURRENCY_PREFIX)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SETTINGS_CURRENCY_PREFIX))
async def set_currency(callback: CallbackQuery, user: User) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    user.base_currency = callback.data.removeprefix(SETTINGS_CURRENCY_PREFIX)

    await callback.message.edit_text(
        f"{texts.SETTINGS_CURRENCY_SAVED}\n\n{texts.settings_overview(user)}",
        reply_markup=settings_menu_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == SETTINGS_TIMEZONE)
async def open_timezone_settings(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        texts.SETTINGS_TIMEZONE_PROMPT, reply_markup=timezone_keyboard(SETTINGS_TIMEZONE_PREFIX)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SETTINGS_TIMEZONE_PREFIX))
async def set_timezone(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    user.timezone = callback.data.removeprefix(SETTINGS_TIMEZONE_PREFIX)
    await _recompute_reminders(session, user)

    await callback.message.edit_text(
        f"{texts.SETTINGS_TIMEZONE_SAVED}\n\n{texts.settings_overview(user)}",
        reply_markup=settings_menu_keyboard(),
    )
    await callback.answer()
