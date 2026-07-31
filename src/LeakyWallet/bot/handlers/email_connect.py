from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.keyboards import (
    EMAIL_DISCONNECT,
    SETTINGS_EMAIL,
    email_settings_keyboard,
    settings_menu_keyboard,
)
from LeakyWallet.config import get_settings
from LeakyWallet.db.models.email_account import EmailProvider
from LeakyWallet.db.models.user import User
from LeakyWallet.mail.oauth import create_auth_url
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.services.email_accounts import EmailAccountService

router = Router(name="email_connect")


@router.callback_query(F.data == SETTINGS_EMAIL)
async def open_email_settings(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert isinstance(callback.message, Message)

    repository = EmailAccountRepository(session)
    existing = await repository.get_by_user_and_provider(user.id, EmailProvider.GMAIL)

    if existing is not None:
        text = texts.EMAIL_CONNECTED_STATUS.format(email=existing.email)
        markup = email_settings_keyboard(connect_url=None)
    elif not get_settings().google_client_id:
        text = texts.EMAIL_NOT_CONFIGURED
        markup = settings_menu_keyboard()
    else:
        url = await create_auth_url(user.id)
        text = texts.EMAIL_NOT_CONNECTED_STATUS
        markup = email_settings_keyboard(connect_url=url)

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == EMAIL_DISCONNECT)
async def disconnect_email(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert isinstance(callback.message, Message)

    repository = EmailAccountRepository(session)
    existing = await repository.get_by_user_and_provider(user.id, EmailProvider.GMAIL)
    if existing is not None:
        service = EmailAccountService(repository)
        await service.disconnect(existing)

    await callback.message.edit_text(
        f"{texts.EMAIL_DISCONNECTED}\n\n{texts.settings_overview(user)}",
        reply_markup=settings_menu_keyboard(),
    )
    await callback.answer()
