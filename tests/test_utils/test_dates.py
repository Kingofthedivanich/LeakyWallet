import datetime

from LeakyWallet.utils.dates import format_date, parse_date_input


def test_parse_date_input_valid() -> None:
    result = parse_date_input("15.08.2026", "Europe/Moscow")
    assert result is not None
    assert result.astimezone(datetime.UTC).date() == datetime.date(2026, 8, 15)


def test_parse_date_input_invalid() -> None:
    assert parse_date_input("not a date", "UTC") is None
    assert parse_date_input("31.02.2026", "UTC") is None
    assert parse_date_input("2026-08-15", "UTC") is None


def test_format_date_roundtrip() -> None:
    value = parse_date_input("01.01.2027", "UTC")
    assert value is not None
    assert format_date(value, "UTC") == "01.01.2027"
