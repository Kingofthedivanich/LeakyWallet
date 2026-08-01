from decimal import Decimal

from LeakyWallet.db.models.subscription import SubscriptionPeriod
from LeakyWallet.utils.money import (
    amounts_are_consistent,
    format_amount,
    monthly_equivalent,
    parse_amount,
    yearly_equivalent,
)


def test_monthly_equivalent_for_each_period() -> None:
    assert monthly_equivalent(Decimal("100"), SubscriptionPeriod.MONTHLY) == Decimal("100.00")
    assert monthly_equivalent(Decimal("1200"), SubscriptionPeriod.YEARLY) == Decimal("100.00")
    assert monthly_equivalent(Decimal("300"), SubscriptionPeriod.QUARTERLY) == Decimal("100.00")


def test_yearly_equivalent_for_each_period() -> None:
    assert yearly_equivalent(Decimal("100"), SubscriptionPeriod.MONTHLY) == Decimal("1200.00")
    assert yearly_equivalent(Decimal("1200"), SubscriptionPeriod.YEARLY) == Decimal("1200.00")
    assert yearly_equivalent(Decimal("300"), SubscriptionPeriod.QUARTERLY) == Decimal("1200.00")


def test_format_amount() -> None:
    assert format_amount(Decimal("9.5"), "USD") == "9.50 USD"


def test_parse_amount_valid() -> None:
    assert parse_amount("299,90") == Decimal("299.90")
    assert parse_amount("10") == Decimal("10.00")


def test_parse_amount_invalid() -> None:
    assert parse_amount("abc") is None
    assert parse_amount("-5") is None
    assert parse_amount("0") is None


def test_amounts_are_consistent_for_fixed_price_subscription() -> None:
    amounts = [Decimal("799.00"), Decimal("799.00"), Decimal("799.00")]
    assert amounts_are_consistent(amounts) is True


def test_amounts_are_consistent_tolerates_one_price_change() -> None:
    # e.g. a genuine plan-price bump mid-history - real data point (GitHub
    # billing) that must NOT be flagged as a random one-off purchase stream.
    amounts = [Decimal("4.00"), Decimal("4.00"), Decimal("1.00")]
    assert amounts_are_consistent(amounts) is True


def test_amounts_are_consistent_false_for_scattered_amounts() -> None:
    # Real data point: unrelated one-off Steam purchases/wallet top-ups that
    # happened to share a domain match, not a fixed-price subscription.
    amounts = [Decimal("1.64"), Decimal("129.00"), Decimal("2.15")]
    assert amounts_are_consistent(amounts) is False
