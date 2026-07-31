import calendar
import datetime
from collections.abc import Sequence
from zoneinfo import ZoneInfo

from LeakyWallet.db.models.subscription import SubscriptionPeriod

_MONTHS_PER_PERIOD: dict[SubscriptionPeriod, int] = {
    SubscriptionPeriod.MONTHLY: 1,
    SubscriptionPeriod.QUARTERLY: 3,
    SubscriptionPeriod.YEARLY: 12,
}


def add_period(value: datetime.datetime, period: SubscriptionPeriod) -> datetime.datetime:
    if period == SubscriptionPeriod.WEEKLY:
        return value + datetime.timedelta(days=7)

    months_to_add = _MONTHS_PER_PERIOD[period]
    total_month_index = value.month - 1 + months_to_add
    year = value.year + total_month_index // 12
    month = total_month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def infer_period_from_intervals(
    charged_dates: Sequence[datetime.datetime],
) -> SubscriptionPeriod | None:
    if len(charged_dates) < 2:
        return None

    sorted_dates = sorted(charged_dates)
    deltas_days = [
        (sorted_dates[i + 1] - sorted_dates[i]).days for i in range(len(sorted_dates) - 1)
    ]
    avg_days = sum(deltas_days) / len(deltas_days)

    if avg_days <= 10:
        return SubscriptionPeriod.WEEKLY
    if avg_days <= 45:
        return SubscriptionPeriod.MONTHLY
    if avg_days <= 120:
        return SubscriptionPeriod.QUARTERLY
    return SubscriptionPeriod.YEARLY


def parse_date_input(text: str, timezone: str) -> datetime.datetime | None:
    parts = text.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        day, month, year = (int(part) for part in parts)
        local_date = datetime.date(year, month, day)
    except ValueError:
        return None

    local_dt = datetime.datetime.combine(
        local_date, datetime.time(hour=12), tzinfo=ZoneInfo(timezone)
    )
    return local_dt.astimezone(datetime.UTC)


def format_date(value: datetime.datetime, timezone: str) -> str:
    local = value.astimezone(ZoneInfo(timezone))
    return local.strftime("%d.%m.%Y")
