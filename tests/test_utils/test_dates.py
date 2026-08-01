import datetime

from LeakyWallet.utils.dates import format_date, has_same_day_repeat, parse_date_input


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


def test_has_same_day_repeat_false_for_distinct_days() -> None:
    dates = [
        datetime.datetime(2026, 2, 5, tzinfo=datetime.UTC),
        datetime.datetime(2026, 2, 12, tzinfo=datetime.UTC),
        datetime.datetime(2026, 6, 19, tzinfo=datetime.UTC),
    ]
    assert has_same_day_repeat(dates) is False


def test_has_same_day_repeat_true_for_same_calendar_date() -> None:
    dates = [
        datetime.datetime(2026, 2, 5, 9, 0, tzinfo=datetime.UTC),
        datetime.datetime(2026, 2, 5, 18, 0, tzinfo=datetime.UTC),  # same day, different time
    ]
    assert has_same_day_repeat(dates) is True
