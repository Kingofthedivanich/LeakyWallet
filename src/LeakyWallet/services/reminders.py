import datetime
from collections.abc import Sequence
from zoneinfo import ZoneInfo

from LeakyWallet.db.models.subscription import Subscription, SubscriptionStatus
from LeakyWallet.db.models.user import ReminderPolicy, User
from LeakyWallet.repositories.reminders import ReminderRepository

DAYS_BEFORE_N = 3
REMINDER_LOCAL_HOUR = 10
DIGEST_WEEKDAY = 0  # Monday
DIGEST_LOCAL_HOUR = 10


def _localize(local_date: datetime.date, hour: int, timezone: str) -> datetime.datetime:
    local_dt = datetime.datetime.combine(
        local_date, datetime.time(hour=hour), tzinfo=ZoneInfo(timezone)
    )
    return local_dt.astimezone(datetime.UTC)


def calculate_days_before_fire_at(
    next_charge_at: datetime.datetime, timezone: str
) -> datetime.datetime:
    local_charge_date = next_charge_at.astimezone(ZoneInfo(timezone)).date()
    fire_date = local_charge_date - datetime.timedelta(days=DAYS_BEFORE_N)
    return _localize(fire_date, REMINDER_LOCAL_HOUR, timezone)


def _next_weekday_on_or_after(start: datetime.date, weekday: int) -> datetime.date:
    days_ahead = (weekday - start.weekday()) % 7
    return start + datetime.timedelta(days=days_ahead)


def calculate_weekly_digest_fire_at(now: datetime.datetime, timezone: str) -> datetime.datetime:
    local_now = now.astimezone(ZoneInfo(timezone))
    candidate_date = _next_weekday_on_or_after(local_now.date(), DIGEST_WEEKDAY)
    fire_at = _localize(candidate_date, DIGEST_LOCAL_HOUR, timezone)
    if fire_at <= now:
        fire_at = _localize(
            candidate_date + datetime.timedelta(days=7), DIGEST_LOCAL_HOUR, timezone
        )
    return fire_at


def _next_month_first(local_date: datetime.date) -> datetime.date:
    if local_date.month == 12:
        return datetime.date(local_date.year + 1, 1, 1)
    return datetime.date(local_date.year, local_date.month + 1, 1)


def calculate_monthly_report_fire_at(now: datetime.datetime, timezone: str) -> datetime.datetime:
    local_now = now.astimezone(ZoneInfo(timezone))
    candidate_date = _next_month_first(local_now.date())
    return _localize(candidate_date, DIGEST_LOCAL_HOUR, timezone)


class ReminderService:
    def __init__(self, repository: ReminderRepository) -> None:
        self._repository = repository

    async def recompute_for_user(
        self, user: User, subscriptions: Sequence[Subscription], now: datetime.datetime
    ) -> None:
        if user.reminder_policy == ReminderPolicy.OFF:
            await self._repository.delete_pending_for_user(user.id)
            return

        if user.reminder_policy == ReminderPolicy.DAYS_BEFORE:
            await self._repository.delete_pending_for_user(
                user.id, kinds={ReminderPolicy.WEEKLY_DIGEST, ReminderPolicy.MONTHLY_REPORT}
            )
            keep_subscription_ids: set[int] = set()
            for subscription in subscriptions:
                if (
                    subscription.status != SubscriptionStatus.ACTIVE
                    or subscription.next_charge_at is None
                ):
                    continue
                fire_at = calculate_days_before_fire_at(subscription.next_charge_at, user.timezone)
                if fire_at <= now:
                    continue
                keep_subscription_ids.add(subscription.id)
                await self._repository.upsert_pending(
                    user_id=user.id,
                    subscription_id=subscription.id,
                    kind=ReminderPolicy.DAYS_BEFORE,
                    fire_at=fire_at,
                )
            await self._repository.delete_stale_days_before(user.id, keep_subscription_ids)
            return

        if user.reminder_policy == ReminderPolicy.WEEKLY_DIGEST:
            await self._repository.delete_pending_for_user(
                user.id, kinds={ReminderPolicy.DAYS_BEFORE, ReminderPolicy.MONTHLY_REPORT}
            )
            fire_at = calculate_weekly_digest_fire_at(now, user.timezone)
            await self._repository.upsert_pending(
                user_id=user.id,
                subscription_id=None,
                kind=ReminderPolicy.WEEKLY_DIGEST,
                fire_at=fire_at,
            )
            return

        if user.reminder_policy == ReminderPolicy.MONTHLY_REPORT:
            await self._repository.delete_pending_for_user(
                user.id, kinds={ReminderPolicy.DAYS_BEFORE, ReminderPolicy.WEEKLY_DIGEST}
            )
            fire_at = calculate_monthly_report_fire_at(now, user.timezone)
            await self._repository.upsert_pending(
                user_id=user.id,
                subscription_id=None,
                kind=ReminderPolicy.MONTHLY_REPORT,
                fire_at=fire_at,
            )
            return
