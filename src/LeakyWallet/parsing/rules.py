import datetime
import re
from decimal import Decimal, InvalidOperation

from LeakyWallet.db.models.subscription import SubscriptionPeriod

_THOUSANDS_SEP = "[  ]"
_NUMBER = rf"\d{{1,3}}(?:{_THOUSANDS_SEP}\d{{3}})*(?:[.,]\d{{1,2}})?"

_AMOUNT_PATTERNS = [
    re.compile(
        rf"(?P<amount>{_NUMBER})\s*(?P<currency>₽|руб\.?|RUB|\$|USD|€|EUR)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?P<currency>₽|\$|€)\s*(?P<amount>{_NUMBER})",
        re.IGNORECASE,
    ),
]

_CURRENCY_SYMBOLS: dict[str, str] = {
    "₽": "RUB",  # ₽
    "руб": "RUB",  # руб
    "rub": "RUB",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",  # €
    "eur": "EUR",
}

_DATE_PATTERN = re.compile(r"(?P<day>\d{1,2})[.\/](?P<month>\d{1,2})[.\/](?P<year>\d{4})")

_PERIOD_KEYWORDS: tuple[tuple[SubscriptionPeriod, tuple[str, ...]], ...] = (
    # Stems (not full words) on purpose, so e.g. "ежемесячную" (accusative)
    # still matches "ежемесячн" - Russian receipts rarely use the bare adverb.
    (SubscriptionPeriod.WEEKLY, ("weekly", "еженедельн", "раз в неделю")),
    (SubscriptionPeriod.MONTHLY, ("monthly", "ежемесячн", "раз в месяц")),
    (SubscriptionPeriod.QUARTERLY, ("quarterly", "квартал")),
    (SubscriptionPeriod.YEARLY, ("yearly", "annual", "ежегодн", "раз в год")),
)


def extract_amount_and_currency(text: str) -> tuple[Decimal, str] | None:
    for pattern in _AMOUNT_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue

        raw_amount = match.group("amount").replace(" ", "").replace(" ", "").replace(",", ".")
        try:
            amount = Decimal(raw_amount)
        except InvalidOperation:
            continue

        currency = _CURRENCY_SYMBOLS.get(match.group("currency").lower().rstrip("."))
        if currency is None or amount <= 0:
            continue

        return amount.quantize(Decimal("0.01")), currency

    return None


def extract_date(text: str) -> datetime.date | None:
    match = _DATE_PATTERN.search(text)
    if match is None:
        return None
    try:
        return datetime.date(
            int(match.group("year")), int(match.group("month")), int(match.group("day"))
        )
    except ValueError:
        return None


def extract_period(text: str) -> SubscriptionPeriod | None:
    text_lower = text.lower()
    for period, keywords in _PERIOD_KEYWORDS:
        if any(keyword in text_lower for keyword in keywords):
            return period
    return None
