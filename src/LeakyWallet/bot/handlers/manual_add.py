from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.handlers.subscriptions import build_subscriptions_list_view
from LeakyWallet.bot.keyboards import (
    ADD_CURRENCY_PREFIX,
    ADD_PERIOD_PREFIX,
    SUBS_ADD,
    currency_keyboard,
    period_keyboard,
)
from LeakyWallet.bot.states import AddSubscriptionStates
from LeakyWallet.db.models.subscription import SubscriptionPeriod
from LeakyWallet.db.models.user import User
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.services.subscriptions import SubscriptionService
from LeakyWallet.utils.dates import parse_date_input
from LeakyWallet.utils.money import parse_amount

router = Router(name="manual_add")


@router.callback_query(F.data == SUBS_ADD)
async def start_add_subscription(callback: CallbackQuery, state: FSMContext) -> None:
    assert isinstance(callback.message, Message)
    await state.set_state(AddSubscriptionStates.entering_name)
    await callback.message.answer(texts.ADD_SUBSCRIPTION_NAME_PROMPT)
    await callback.answer()


@router.message(AddSubscriptionStates.entering_name)
async def on_name_entered(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer(texts.ADD_SUBSCRIPTION_NAME_PROMPT)
        return

    await state.update_data(custom_name=name)
    await state.set_state(AddSubscriptionStates.entering_amount)
    await message.answer(texts.ADD_SUBSCRIPTION_AMOUNT_PROMPT)


@router.message(AddSubscriptionStates.entering_amount)
async def on_amount_entered(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text or "")
    if amount is None:
        await message.answer(texts.INVALID_AMOUNT)
        return

    await state.update_data(amount=str(amount))
    await state.set_state(AddSubscriptionStates.choosing_currency)
    await message.answer(
        texts.ADD_SUBSCRIPTION_CURRENCY_PROMPT, reply_markup=currency_keyboard(ADD_CURRENCY_PREFIX)
    )


@router.callback_query(
    AddSubscriptionStates.choosing_currency, F.data.startswith(ADD_CURRENCY_PREFIX)
)
async def on_currency_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    currency = callback.data.removeprefix(ADD_CURRENCY_PREFIX)
    await state.update_data(currency=currency)
    await state.set_state(AddSubscriptionStates.choosing_period)
    await callback.message.edit_text(
        texts.ADD_SUBSCRIPTION_PERIOD_PROMPT, reply_markup=period_keyboard(ADD_PERIOD_PREFIX)
    )
    await callback.answer()


@router.callback_query(AddSubscriptionStates.choosing_period, F.data.startswith(ADD_PERIOD_PREFIX))
async def on_period_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    period = callback.data.removeprefix(ADD_PERIOD_PREFIX)
    await state.update_data(period=period)
    await state.set_state(AddSubscriptionStates.entering_next_charge_at)
    await callback.message.edit_text(texts.ADD_SUBSCRIPTION_DATE_PROMPT)
    await callback.answer()


@router.message(AddSubscriptionStates.entering_next_charge_at)
async def on_date_entered(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    next_charge_at = parse_date_input(message.text or "", user.timezone)
    if next_charge_at is None:
        await message.answer(texts.INVALID_DATE)
        return

    data = await state.get_data()
    service = SubscriptionService(SubscriptionRepository(session))
    await service.create(
        user_id=user.id,
        custom_name=data["custom_name"],
        amount=Decimal(data["amount"]),
        currency=data["currency"],
        period=SubscriptionPeriod(data["period"]),
        next_charge_at=next_charge_at,
    )
    await state.clear()

    await message.answer(texts.ADD_SUBSCRIPTION_DONE)
    list_text, list_markup = await build_subscriptions_list_view(session, user, page=0)
    await message.answer(list_text, reply_markup=list_markup)
