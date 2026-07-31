from collections.abc import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from LeakyWallet.bot import texts
from LeakyWallet.db.models.subscription import Subscription, SubscriptionPeriod

TIMEZONE_CHOICES: list[tuple[str, str]] = [
    ("Калининград (UTC+2)", "Europe/Kaliningrad"),
    ("Москва (UTC+3)", "Europe/Moscow"),
    ("Самара (UTC+4)", "Europe/Samara"),
    ("Екатеринбург (UTC+5)", "Asia/Yekaterinburg"),
    ("Омск (UTC+6)", "Asia/Omsk"),
    ("Красноярск (UTC+7)", "Asia/Krasnoyarsk"),
    ("Иркутск (UTC+8)", "Asia/Irkutsk"),
    ("Владивосток (UTC+10)", "Asia/Vladivostok"),
    ("UTC", "UTC"),
]

CURRENCY_CHOICES: list[tuple[str, str]] = [
    ("₽ RUB", "RUB"),
    ("$ USD", "USD"),
    ("€ EUR", "EUR"),
]

PERIOD_CHOICES: list[tuple[str, str]] = [
    ("Раз в неделю", SubscriptionPeriod.WEEKLY.value),
    ("Раз в месяц", SubscriptionPeriod.MONTHLY.value),
    ("Раз в квартал", SubscriptionPeriod.QUARTERLY.value),
    ("Раз в год", SubscriptionPeriod.YEARLY.value),
]

PAGE_SIZE = 5

ONBOARDING_TIMEZONE_PREFIX = "onboarding:timezone:"
ONBOARDING_CURRENCY_PREFIX = "onboarding:currency:"
MENU_SUBSCRIPTIONS = "menu:subscriptions"
MENU_SETTINGS = "menu:settings"

SUBS_ADD = "subs:add"
SUBS_LIST_PREFIX = "subs:list:"
SUBS_CARD_PREFIX = "subs:card:"
SUBS_EDIT_PREFIX = "subs:edit:"
SUBS_EDIT_FIELD_PREFIX = "subs:editf:"
SUBS_DELETE_PREFIX = "subs:del:"
SUBS_DELETE_CONFIRM_PREFIX = "subs:delyes:"
SUBS_DELETE_CANCEL_PREFIX = "subs:delno:"
NOOP = "noop"

ADD_CURRENCY_PREFIX = "subsadd:currency:"
ADD_PERIOD_PREFIX = "subsadd:period:"
EDIT_CURRENCY_PREFIX = "subsedit:currency:"
EDIT_PERIOD_PREFIX = "subsedit:period:"

EDIT_FIELD_NAME = "name"
EDIT_FIELD_AMOUNT = "amount"
EDIT_FIELD_PERIOD = "period"
EDIT_FIELD_DATE = "date"


def timezone_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in TIMEZONE_CHOICES:
        builder.button(text=label, callback_data=f"{ONBOARDING_TIMEZONE_PREFIX}{value}")
    builder.adjust(2)
    return builder.as_markup()


def currency_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in CURRENCY_CHOICES:
        builder.button(text=label, callback_data=f"{prefix}{value}")
    builder.adjust(3)
    return builder.as_markup()


def period_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in PERIOD_CHOICES:
        builder.button(text=label, callback_data=f"{prefix}{value}")
    builder.adjust(2)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.MAIN_MENU_SUBSCRIPTIONS, callback_data=MENU_SUBSCRIPTIONS)
    builder.button(text=texts.MAIN_MENU_SETTINGS, callback_data=MENU_SETTINGS)
    builder.adjust(1)
    return builder.as_markup()


def subscriptions_list_keyboard(
    subscriptions: Sequence[Subscription], page: int, total_pages: int
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for subscription in subscriptions:
        name = subscription.custom_name or "Подписка"
        label = f"{name} — {subscription.amount} {subscription.currency}"
        builder.button(text=label, callback_data=f"{SUBS_CARD_PREFIX}{subscription.id}")
    builder.adjust(1)

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="◀️", callback_data=f"{SUBS_LIST_PREFIX}{page - 1}")
        )
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data=NOOP))
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(text="▶️", callback_data=f"{SUBS_LIST_PREFIX}{page + 1}")
        )
    if nav_row:
        builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="➕ Добавить подписку", callback_data=SUBS_ADD))
    return builder.as_markup()


def subscription_card_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Изменить", callback_data=f"{SUBS_EDIT_PREFIX}{subscription_id}")
    builder.button(text="🗑 Удалить", callback_data=f"{SUBS_DELETE_PREFIX}{subscription_id}")
    builder.button(text="◀️ К списку", callback_data=f"{SUBS_LIST_PREFIX}0")
    builder.adjust(2, 1)
    return builder.as_markup()


def edit_field_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Название",
        callback_data=f"{SUBS_EDIT_FIELD_PREFIX}{subscription_id}:{EDIT_FIELD_NAME}",
    )
    builder.button(
        text="Сумма и валюта",
        callback_data=f"{SUBS_EDIT_FIELD_PREFIX}{subscription_id}:{EDIT_FIELD_AMOUNT}",
    )
    builder.button(
        text="Периодичность",
        callback_data=f"{SUBS_EDIT_FIELD_PREFIX}{subscription_id}:{EDIT_FIELD_PERIOD}",
    )
    builder.button(
        text="Дата списания",
        callback_data=f"{SUBS_EDIT_FIELD_PREFIX}{subscription_id}:{EDIT_FIELD_DATE}",
    )
    builder.button(text="◀️ Назад", callback_data=f"{SUBS_CARD_PREFIX}{subscription_id}")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirm_keyboard(subscription_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Да, удалить", callback_data=f"{SUBS_DELETE_CONFIRM_PREFIX}{subscription_id}"
    )
    builder.button(text="Отмена", callback_data=f"{SUBS_DELETE_CANCEL_PREFIX}{subscription_id}")
    builder.adjust(2)
    return builder.as_markup()
