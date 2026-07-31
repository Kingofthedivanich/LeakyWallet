import datetime
from decimal import Decimal

from LeakyWallet.db.models.subscription import SubscriptionPeriod
from LeakyWallet.parsing.rules import extract_amount_and_currency, extract_date, extract_period


def test_extract_amount_rub_symbol() -> None:
    result = extract_amount_and_currency("Списано 799,00 ₽ за подписку")
    assert result == (Decimal("799.00"), "RUB")


def test_extract_amount_thousands_separator() -> None:
    result = extract_amount_and_currency("Списано 2 990,00 руб. за годовую подписку")
    assert result == (Decimal("2990.00"), "RUB")


def test_extract_amount_usd_symbol_prefix() -> None:
    result = extract_amount_and_currency("You were charged $10.99 today")
    assert result == (Decimal("10.99"), "USD")


def test_extract_amount_eur_word() -> None:
    result = extract_amount_and_currency("Payment charged: 4.99 EUR for your plan")
    assert result == (Decimal("4.99"), "EUR")


def test_extract_amount_returns_none_when_absent() -> None:
    assert extract_amount_and_currency("No pricing information here") is None


def test_extract_amount_rejects_zero() -> None:
    assert extract_amount_and_currency("Списано 0,00 ₽ за подписку") is None


def test_extract_date_dd_mm_yyyy() -> None:
    assert extract_date("Дата платежа: 01.08.2026.") == datetime.date(2026, 8, 1)


def test_extract_date_returns_none_when_absent() -> None:
    assert extract_date("no date mentioned") is None


def test_extract_period_monthly_ru() -> None:
    assert extract_period("за ежемесячную подписку Netflix") == SubscriptionPeriod.MONTHLY


def test_extract_period_yearly_ru() -> None:
    assert extract_period("Продлевается раз в год.") == SubscriptionPeriod.YEARLY


def test_extract_period_quarterly() -> None:
    assert extract_period("Billed quarterly for your plan") == SubscriptionPeriod.QUARTERLY


def test_extract_period_returns_none_when_absent() -> None:
    assert extract_period("no period keywords here") is None
