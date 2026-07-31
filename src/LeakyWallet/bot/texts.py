from collections.abc import Sequence

from LeakyWallet.db.models.subscription import Subscription
from LeakyWallet.db.models.user import User
from LeakyWallet.services.reminders import DAYS_BEFORE_N
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
    subscriptions: Sequence[Subscription],
    summary: SubscriptionSummary,
    base_currency: str,
    title: str = SUBSCRIPTIONS_LIST_TITLE,
) -> str:
    lines = [title, ""]
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


WEEKLY_DIGEST_HEADER = "🗓 Еженедельный дайджест подписок"
MONTHLY_REPORT_HEADER = "📊 Отчёт за месяц"


def format_days_before_reminder(subscription: Subscription, timezone: str) -> str:
    name = subscription.custom_name or "Подписка"
    amount = format_amount(subscription.amount, subscription.currency)
    next_charge = (
        format_date(subscription.next_charge_at, timezone)
        if subscription.next_charge_at is not None
        else ""
    )
    return f"⏰ Через {DAYS_BEFORE_N} дня спишут за «{name}»: {amount} ({next_charge})"


SETTINGS_REMINDERS_PROMPT = "Как присылать напоминания?"
SETTINGS_REMINDER_POLICY_SAVED = "Настройки напоминаний сохранены."
SETTINGS_CURRENCY_PROMPT = "В какой валюте считать траты?"
SETTINGS_CURRENCY_SAVED = "Валюта обновлена."
SETTINGS_TIMEZONE_PROMPT = "В каком часовом поясе ты находишься?"
SETTINGS_TIMEZONE_SAVED = "Часовой пояс обновлён."

REMINDER_POLICY_LABELS: dict[str, str] = {
    "off": "выключены",
    "days_before": f"за {DAYS_BEFORE_N} дня до списания",
    "weekly_digest": "еженедельный дайджест",
    "monthly_report": "ежемесячный отчёт",
}


def settings_overview(user: User) -> str:
    policy_label = REMINDER_POLICY_LABELS.get(
        user.reminder_policy.value, user.reminder_policy.value
    )
    return (
        f"{MAIN_MENU_SETTINGS}\n\n"
        f"Валюта: {user.base_currency}\n"
        f"Часовой пояс: {user.timezone}\n"
        f"Напоминания: {policy_label}"
    )


EMAIL_NOT_CONNECTED_STATUS = (
    "Почта не подключена.\n\n"
    "Подключим Gmail только на чтение — мы не сможем ничего отправлять "
    "или удалять от твоего имени."
)
EMAIL_CONNECTED_STATUS = "Подключена: {email}"
EMAIL_NOT_CONFIGURED = "Подключение почты пока не настроено на сервере."
EMAIL_DISCONNECTED = "Почта отключена, токен удалён."

EMAIL_CALLBACK_SUCCESS_HTML = "<h1>Почта подключена!</h1><p>Вернись в Telegram — бот уже знает.</p>"
EMAIL_CALLBACK_ERROR_HTML = "<h1>Не удалось подключить почту</h1><p>{detail}</p>"
EMAIL_CALLBACK_EXPIRED_HTML = "<h1>Ссылка устарела</h1><p>Начни подключение заново в боте.</p>"

EMAIL_CONNECTED_DM = "Готово! Почта {email} подключена."
