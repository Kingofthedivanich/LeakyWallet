from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.keyboards import (
    MENU_SETTINGS,
    ONBOARDING_CURRENCY_PREFIX,
    ONBOARDING_TIMEZONE_PREFIX,
    currency_keyboard,
    main_menu_keyboard,
    timezone_keyboard,
)
from LeakyWallet.bot.states import OnboardingStates
from LeakyWallet.db.models.user import User

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: User) -> None:
    await state.set_state(OnboardingStates.choosing_timezone)
    await message.answer(texts.START_GREETING)
    await message.answer(texts.CHOOSE_TIMEZONE, reply_markup=timezone_keyboard())


@router.callback_query(
    OnboardingStates.choosing_timezone, F.data.startswith(ONBOARDING_TIMEZONE_PREFIX)
)
async def on_timezone_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    timezone = callback.data.removeprefix(ONBOARDING_TIMEZONE_PREFIX)
    await state.update_data(timezone=timezone)
    await state.set_state(OnboardingStates.choosing_currency)

    await callback.message.edit_text(
        texts.CHOOSE_CURRENCY, reply_markup=currency_keyboard(ONBOARDING_CURRENCY_PREFIX)
    )
    await callback.answer()


@router.callback_query(
    OnboardingStates.choosing_currency, F.data.startswith(ONBOARDING_CURRENCY_PREFIX)
)
async def on_currency_chosen(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    currency = callback.data.removeprefix(ONBOARDING_CURRENCY_PREFIX)
    onboarding_data = await state.get_data()
    timezone = onboarding_data["timezone"]

    user.timezone = timezone
    user.base_currency = currency
    await session.flush()

    await state.clear()
    await callback.message.edit_text(texts.ONBOARDING_DONE)
    await callback.message.answer(texts.MAIN_MENU_TITLE, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data == MENU_SETTINGS)
async def on_main_menu_stub(callback: CallbackQuery) -> None:
    await callback.answer(texts.FEATURE_NOT_READY, show_alert=True)
