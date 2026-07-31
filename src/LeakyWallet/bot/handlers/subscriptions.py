from decimal import Decimal
from typing import cast

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.keyboards import (
    EDIT_CURRENCY_PREFIX,
    EDIT_FIELD_AMOUNT,
    EDIT_FIELD_DATE,
    EDIT_FIELD_NAME,
    EDIT_FIELD_PERIOD,
    EDIT_PERIOD_PREFIX,
    MENU_SUBSCRIPTIONS,
    NOOP,
    PAGE_SIZE,
    SUBS_CARD_PREFIX,
    SUBS_DELETE_CANCEL_PREFIX,
    SUBS_DELETE_CONFIRM_PREFIX,
    SUBS_DELETE_PREFIX,
    SUBS_EDIT_FIELD_PREFIX,
    SUBS_EDIT_PREFIX,
    SUBS_LIST_PREFIX,
    currency_keyboard,
    delete_confirm_keyboard,
    edit_field_keyboard,
    period_keyboard,
    subscription_card_keyboard,
    subscriptions_list_keyboard,
)
from LeakyWallet.bot.states import EditSubscriptionStates
from LeakyWallet.db.models.subscription import Subscription, SubscriptionPeriod
from LeakyWallet.db.models.user import User
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.services.subscriptions import SubscriptionService
from LeakyWallet.utils.dates import parse_date_input
from LeakyWallet.utils.money import parse_amount

router = Router(name="subscriptions")


async def build_subscriptions_list_view(
    session: AsyncSession, user: User, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    service = SubscriptionService(SubscriptionRepository(session))
    subscriptions = await service.list_visible(user.id)

    if not subscriptions:
        return texts.SUBSCRIPTIONS_EMPTY, subscriptions_list_keyboard([], 0, 1)

    total_pages = max(1, (len(subscriptions) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    page_items = subscriptions[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    summary = await service.summary(user.id, user.base_currency)
    text = texts.format_subscriptions_list(page_items, summary, user.base_currency)
    return text, subscriptions_list_keyboard(page_items, page, total_pages)


def _subscription_id_from(data: str, prefix: str) -> int:
    return int(data.removeprefix(prefix))


async def _get_owned_or_notify(
    callback: CallbackQuery, session: AsyncSession, user: User, subscription_id: int
) -> Subscription | None:
    service = SubscriptionService(SubscriptionRepository(session))
    subscription = await service.get_owned(subscription_id, user.id)
    if subscription is None:
        await callback.answer(texts.SUBSCRIPTION_NOT_FOUND, show_alert=True)
    return subscription


@router.callback_query(F.data == NOOP)
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == MENU_SUBSCRIPTIONS)
async def open_subscriptions_list(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    assert isinstance(callback.message, Message)
    text, markup = await build_subscriptions_list_view(session, user, page=0)
    await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_LIST_PREFIX))
async def paginate_subscriptions_list(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    page = _subscription_id_from(callback.data, SUBS_LIST_PREFIX)
    text, markup = await build_subscriptions_list_view(session, user, page)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_CARD_PREFIX))
async def open_subscription_card(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    subscription_id = _subscription_id_from(callback.data, SUBS_CARD_PREFIX)
    subscription = await _get_owned_or_notify(callback, session, user, subscription_id)
    if subscription is None:
        return

    text = texts.format_subscription_card(subscription, user.timezone)
    await callback.message.edit_text(text, reply_markup=subscription_card_keyboard(subscription.id))
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_DELETE_PREFIX))
async def ask_delete_confirmation(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    subscription_id = _subscription_id_from(callback.data, SUBS_DELETE_PREFIX)
    subscription = await _get_owned_or_notify(callback, session, user, subscription_id)
    if subscription is None:
        return

    name = subscription.custom_name or "подписку"
    await callback.message.edit_text(
        texts.DELETE_CONFIRM_PROMPT.format(name=name),
        reply_markup=delete_confirm_keyboard(subscription.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_DELETE_CONFIRM_PREFIX))
async def confirm_delete(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    subscription_id = _subscription_id_from(callback.data, SUBS_DELETE_CONFIRM_PREFIX)
    subscription = await _get_owned_or_notify(callback, session, user, subscription_id)
    if subscription is None:
        return

    service = SubscriptionService(SubscriptionRepository(session))
    await service.delete(subscription)

    text, markup = await build_subscriptions_list_view(session, user, page=0)
    await callback.message.edit_text(f"{texts.DELETE_DONE}\n\n{text}", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_DELETE_CANCEL_PREFIX))
async def cancel_delete(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    subscription_id = _subscription_id_from(callback.data, SUBS_DELETE_CANCEL_PREFIX)
    subscription = await _get_owned_or_notify(callback, session, user, subscription_id)
    if subscription is None:
        return

    text = texts.format_subscription_card(subscription, user.timezone)
    await callback.message.edit_text(text, reply_markup=subscription_card_keyboard(subscription.id))
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_EDIT_PREFIX))
async def open_edit_menu(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    subscription_id = _subscription_id_from(callback.data, SUBS_EDIT_PREFIX)
    subscription = await _get_owned_or_notify(callback, session, user, subscription_id)
    if subscription is None:
        return

    await callback.message.edit_text(
        texts.EDIT_FIELD_PROMPT, reply_markup=edit_field_keyboard(subscription.id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(SUBS_EDIT_FIELD_PREFIX))
async def choose_edit_field(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    remainder = callback.data.removeprefix(SUBS_EDIT_FIELD_PREFIX)
    id_part, _, field = remainder.partition(":")
    subscription = await _get_owned_or_notify(callback, session, user, int(id_part))
    if subscription is None:
        return

    await state.update_data(subscription_id=subscription.id)

    if field == EDIT_FIELD_NAME:
        await state.set_state(EditSubscriptionStates.entering_name)
        await callback.message.edit_text(texts.EDIT_NAME_PROMPT)
    elif field == EDIT_FIELD_AMOUNT:
        await state.set_state(EditSubscriptionStates.entering_amount)
        await callback.message.edit_text(texts.EDIT_AMOUNT_PROMPT)
    elif field == EDIT_FIELD_PERIOD:
        await state.set_state(EditSubscriptionStates.choosing_period)
        await callback.message.edit_text(
            texts.EDIT_PERIOD_PROMPT, reply_markup=period_keyboard(EDIT_PERIOD_PREFIX)
        )
    elif field == EDIT_FIELD_DATE:
        await state.set_state(EditSubscriptionStates.entering_date)
        await callback.message.edit_text(texts.EDIT_DATE_PROMPT)
    await callback.answer()


async def _load_editing_subscription(
    state: FSMContext, session: AsyncSession, user: User
) -> Subscription | None:
    data = await state.get_data()
    subscription_id = data.get("subscription_id")
    if subscription_id is None:
        return None
    service = SubscriptionService(SubscriptionRepository(session))
    return await service.get_owned(cast(int, subscription_id), user.id)


@router.message(EditSubscriptionStates.entering_name)
async def apply_name_edit(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer(texts.EDIT_NAME_PROMPT)
        return

    subscription = await _load_editing_subscription(state, session, user)
    if subscription is None:
        await message.answer(texts.SUBSCRIPTION_NOT_FOUND)
        await state.clear()
        return

    service = SubscriptionService(SubscriptionRepository(session))
    await service.update(subscription, custom_name=name)
    await state.clear()
    await message.answer(texts.EDIT_DONE)
    await message.answer(
        texts.format_subscription_card(subscription, user.timezone),
        reply_markup=subscription_card_keyboard(subscription.id),
    )


@router.message(EditSubscriptionStates.entering_amount)
async def apply_amount_edit(message: Message, state: FSMContext) -> None:
    amount = parse_amount(message.text or "")
    if amount is None:
        await message.answer(texts.INVALID_AMOUNT)
        return

    await state.update_data(pending_amount=str(amount))
    await state.set_state(EditSubscriptionStates.choosing_currency)
    await message.answer(
        texts.EDIT_CURRENCY_PROMPT, reply_markup=currency_keyboard(EDIT_CURRENCY_PREFIX)
    )


@router.callback_query(
    EditSubscriptionStates.choosing_currency, F.data.startswith(EDIT_CURRENCY_PREFIX)
)
async def apply_currency_edit(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    currency = callback.data.removeprefix(EDIT_CURRENCY_PREFIX)
    data = await state.get_data()
    amount = Decimal(data["pending_amount"])

    subscription = await _load_editing_subscription(state, session, user)
    if subscription is None:
        await callback.answer(texts.SUBSCRIPTION_NOT_FOUND, show_alert=True)
        await state.clear()
        return

    service = SubscriptionService(SubscriptionRepository(session))
    await service.update(subscription, amount=amount, currency=currency)
    await state.clear()
    await callback.message.edit_text(
        f"{texts.EDIT_DONE}\n\n{texts.format_subscription_card(subscription, user.timezone)}",
        reply_markup=subscription_card_keyboard(subscription.id),
    )
    await callback.answer()


@router.callback_query(
    EditSubscriptionStates.choosing_period, F.data.startswith(EDIT_PERIOD_PREFIX)
)
async def apply_period_edit(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    assert callback.data is not None
    assert isinstance(callback.message, Message)

    period = callback.data.removeprefix(EDIT_PERIOD_PREFIX)
    subscription = await _load_editing_subscription(state, session, user)
    if subscription is None:
        await callback.answer(texts.SUBSCRIPTION_NOT_FOUND, show_alert=True)
        await state.clear()
        return

    service = SubscriptionService(SubscriptionRepository(session))
    await service.update(subscription, period=SubscriptionPeriod(period))
    await state.clear()
    await callback.message.edit_text(
        f"{texts.EDIT_DONE}\n\n{texts.format_subscription_card(subscription, user.timezone)}",
        reply_markup=subscription_card_keyboard(subscription.id),
    )
    await callback.answer()


@router.message(EditSubscriptionStates.entering_date)
async def apply_date_edit(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    next_charge_at = parse_date_input(message.text or "", user.timezone)
    if next_charge_at is None:
        await message.answer(texts.INVALID_DATE)
        return

    subscription = await _load_editing_subscription(state, session, user)
    if subscription is None:
        await message.answer(texts.SUBSCRIPTION_NOT_FOUND)
        await state.clear()
        return

    service = SubscriptionService(SubscriptionRepository(session))
    await service.update(subscription, next_charge_at=next_charge_at)
    await state.clear()
    await message.answer(texts.EDIT_DONE)
    await message.answer(
        texts.format_subscription_card(subscription, user.timezone),
        reply_markup=subscription_card_keyboard(subscription.id),
    )
