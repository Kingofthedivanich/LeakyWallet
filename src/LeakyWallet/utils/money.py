from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from LeakyWallet.db.models.subscription import SubscriptionPeriod

_MONTHLY_FACTOR: dict[SubscriptionPeriod, Decimal] = {
    SubscriptionPeriod.WEEKLY: Decimal("52") / Decimal("12"),
    SubscriptionPeriod.MONTHLY: Decimal("1"),
    SubscriptionPeriod.QUARTERLY: Decimal("1") / Decimal("3"),
    SubscriptionPeriod.YEARLY: Decimal("1") / Decimal("12"),
}

_YEARLY_FACTOR: dict[SubscriptionPeriod, Decimal] = {
    SubscriptionPeriod.WEEKLY: Decimal("52"),
    SubscriptionPeriod.MONTHLY: Decimal("12"),
    SubscriptionPeriod.QUARTERLY: Decimal("4"),
    SubscriptionPeriod.YEARLY: Decimal("1"),
}


def monthly_equivalent(amount: Decimal, period: SubscriptionPeriod) -> Decimal:
    return (amount * _MONTHLY_FACTOR[period]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def yearly_equivalent(amount: Decimal, period: SubscriptionPeriod) -> Decimal:
    return (amount * _YEARLY_FACTOR[period]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_amount(amount: Decimal, currency: str) -> str:
    return f"{amount:.2f} {currency}"


def parse_amount(text: str) -> Decimal | None:
    normalized = text.strip().replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    return amount.quantize(Decimal("0.01"))
