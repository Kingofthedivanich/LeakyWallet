from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from LeakyWallet.db.models.subscription import SubscriptionPeriod

# A fixed-price subscription's charges barely move (rounding, one price
# change). Above this coefficient of variation (stddev / mean), amounts are
# scattered enough to be one-off purchases rather than recurring billing -
# calibrated against a live dataset: a real ~$4->$4->$1 GitHub price change
# sits at ~0.47 CV, unrelated Steam purchases at ~1.6, unrelated Yandex
# purchases at ~5.6.
AMOUNT_CV_THRESHOLD = Decimal("0.5")

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


def amounts_are_consistent(amounts: Sequence[Decimal]) -> bool:
    mean = sum(amounts, Decimal("0")) / len(amounts)
    if mean == 0:
        return True
    variance = sum(((a - mean) ** 2 for a in amounts), Decimal("0")) / len(amounts)
    coefficient_of_variation = variance.sqrt() / mean
    return coefficient_of_variation <= AMOUNT_CV_THRESHOLD


def parse_amount(text: str) -> Decimal | None:
    normalized = text.strip().replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    return amount.quantize(Decimal("0.01"))
