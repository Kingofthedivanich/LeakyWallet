from collections.abc import Sequence

from LeakyWallet.db.models.subscription import Subscription
from LeakyWallet.services.subscriptions import SubscriptionSummary
from LeakyWallet.utils.dates import format_date
from LeakyWallet.utils.money import format_amount

START_GREETING = (
    "Привет! Я слежу за подписками, на которые ты тратишь деньги, "
    "и напоминаю о списаниях.\n\nДавай настроим пару вещей."
)
CHOOSE_TIMEZONE = "В каком часовом поясе ты находишься?"
CHOOSE_CURRENCY = "В какой валюте будем считать траты?"
ONBOARDING_DONE = "Готово! Вот твоё главное меню."

MAIN_MENU_TITLE = "Главное меню"
MAIN_MENU_SUBSCRIPTIONS = "Мои подписки"
MAIN_MENU_SETTINGS = "Настройки"
FEATURE_NOT_READY = "Этот раздел ещё в разработке — скоро появится."

ADD_SUBSCRIPTION_NAME_PROMPT = "Как называется подписка?"
ADD_SUBSCRIPTION_AMOUNT_PROMPT = "Сколько стоит списание? Введи число, например 299.90"
ADD_SUBSCRIPTION_CURRENCY_PROMPT = "В какой валюте?"
ADD_SUBSCRIPTION_PERIOD_PROMPT = "Как часто списывают деньги?"
ADD_SUBSCRIPTION_DATE_PROMPT = "Когда следующее списание? Введи дату в формате ДД.ММ.ГГГГ"
ADD_SUBSCRIPTION_DONE = "Подписка добавлена."

INVALID_AMOUNT = "Не понял сумму. Введи число, например 299.90"
INVALID_DATE = "Не понял дату. Введи в формате ДД.ММ.ГГГГ, например 15.08.2026"

SUBSCRIPTIONS_EMPTY = "Пока нет ни одной подписки. Добавь первую!"
SUBSCRIPTIONS_LIST_TITLE = "Твои подписки:"
SUBSCRIPTION_NOT_FOUND = "Подписка не найдена."

EDIT_FIELD_PROMPT = "Что изменить?"
EDIT_NAME_PROMPT = "Введи новое название."
EDIT_AMOUNT_PROMPT = "Введи новую сумму, например 299.90"
EDIT_CURRENCY_PROMPT = "В какой валюте?"
EDIT_PERIOD_PROMPT = "Как часто списывают деньги?"
EDIT_DATE_PROMPT = "Введи новую дату списания в формате ДД.ММ.ГГГГ"
EDIT_DONE = "Изменения сохранены."

DELETE_CONFIRM_PROMPT = "Удалить подписку «{name}»?"
DELETE_DONE = "Подписка удалена."

PERIOD_LABELS: dict[str, str] = {
    "weekly": "раз в неделю",
    "monthly": "раз в месяц",
    "quarterly": "раз в квартал",
    "yearly": "раз в год",
}


def format_subscription_card(subscription: Subscription, timezone: str) -> str:
    name = subscription.custom_name or "Подписка"
    period_label = PERIOD_LABELS.get(subscription.period.value, subscription.period.value)
    next_charge = (
        format_date(subscription.next_charge_at, timezone)
        if subscription.next_charge_at is not None
        else "не указана"
    )
    return (
        f"<b>{name}</b>\n"
        f"Сумма: {format_amount(subscription.amount, subscription.currency)}\n"
        f"Периодичность: {period_label}\n"
        f"Следующее списание: {next_charge}"
    )


def format_subscriptions_list(
    subscriptions: Sequence[Subscription], summary: SubscriptionSummary, base_currency: str
) -> str:
    lines = [SUBSCRIPTIONS_LIST_TITLE, ""]
    for subscription in subscriptions:
        name = subscription.custom_name or "Подписка"
        period_label = PERIOD_LABELS.get(subscription.period.value, subscription.period.value)
        amount = format_amount(subscription.amount, subscription.currency)
        lines.append(f"• {name} — {amount} ({period_label})")

    lines.append("")
    lines.append(f"В месяц: {format_amount(summary.monthly_total, base_currency)}")
    lines.append(f"В год: {format_amount(summary.yearly_total, base_currency)}")
    if summary.other_currencies:
        currencies = ", ".join(sorted(summary.other_currencies))
        lines.append(f"Есть подписки в других валютах ({currencies}) — не учтены в сумме.")

    return "\n".join(lines)
