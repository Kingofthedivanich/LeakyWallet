import datetime
from zoneinfo import ZoneInfo


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
