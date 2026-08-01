from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.keyboards import (
    PRIVACY_EXPORT,
    PRIVACY_WIPE,
    PRIVACY_WIPE_CANCEL,
    PRIVACY_WIPE_CONFIRM,
    SETTINGS_PRIVACY,
    privacy_menu_keyboard,
    settings_menu_keyboard,
    wipe_confirm_keyboard,
)
from LeakyWallet.db.models.user import User
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.export import transactions_to_csv

router = Router(name="privacy")


@router.callback_query(F.data == SETTINGS_PRIVACY)
async def open_privacy_menu(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        texts.PRIVACY_WHAT_WE_STORE, reply_markup=privacy_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == PRIVACY_EXPORT)
async def export_csv(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert isinstance(callback.message, Message)

    transactions = await TransactionRepository(session).list_by_user(user.id)
    if not transactions:
        await callback.answer(texts.PRIVACY_EXPORT_EMPTY, show_alert=True)
        return

    csv_text = transactions_to_csv(transactions)
    document = BufferedInputFile(csv_text.encode("utf-8"), filename=texts.PRIVACY_EXPORT_FILENAME)
    await callback.message.answer_document(document, caption=texts.PRIVACY_EXPORT_CAPTION)
    await callback.answer()


@router.message(Command("wipe"))
async def cmd_wipe(message: Message) -> None:
    await message.answer(texts.WIPE_CONFIRM_PROMPT, reply_markup=wipe_confirm_keyboard())


@router.callback_query(F.data == PRIVACY_WIPE)
async def open_wipe_confirm(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(
        texts.WIPE_CONFIRM_PROMPT, reply_markup=wipe_confirm_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == PRIVACY_WIPE_CANCEL)
async def cancel_wipe(callback: CallbackQuery) -> None:
    assert isinstance(callback.message, Message)
    await callback.message.edit_text(texts.WIPE_CANCELLED, reply_markup=settings_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == PRIVACY_WIPE_CONFIRM)
async def confirm_wipe(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert isinstance(callback.message, Message)

    await UserRepository(session).delete(user)

    await callback.message.edit_text(texts.WIPE_DONE)
    await callback.answer()
