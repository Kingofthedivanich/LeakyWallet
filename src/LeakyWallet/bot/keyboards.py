from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from LeakyWallet.bot import texts

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

ONBOARDING_TIMEZONE_PREFIX = "onboarding:timezone:"
ONBOARDING_CURRENCY_PREFIX = "onboarding:currency:"
MENU_SUBSCRIPTIONS = "menu:subscriptions"
MENU_SETTINGS = "menu:settings"


def timezone_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in TIMEZONE_CHOICES:
        builder.button(text=label, callback_data=f"{ONBOARDING_TIMEZONE_PREFIX}{value}")
    builder.adjust(2)
    return builder.as_markup()


def currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in CURRENCY_CHOICES:
        builder.button(text=label, callback_data=f"{ONBOARDING_CURRENCY_PREFIX}{value}")
    builder.adjust(3)
    return builder.as_markup()


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.MAIN_MENU_SUBSCRIPTIONS, callback_data=MENU_SUBSCRIPTIONS)
    builder.button(text=texts.MAIN_MENU_SETTINGS, callback_data=MENU_SETTINGS)
    builder.adjust(1)
    return builder.as_markup()
