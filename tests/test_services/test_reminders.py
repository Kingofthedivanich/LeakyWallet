import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.reminder import Reminder
from LeakyWallet.db.models.subscription import (
    SubscriptionPeriod,
    SubscriptionSource,
    SubscriptionStatus,
)
from LeakyWallet.db.models.user import ReminderPolicy
from LeakyWallet.repositories.reminders import ReminderRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.reminders import (
    DAYS_BEFORE_N,
    DIGEST_LOCAL_HOUR,
    REMINDER_LOCAL_HOUR,
    ReminderService,
    calculate_days_before_fire_at,
    calculate_monthly_report_fire_at,
    calculate_weekly_digest_fire_at,
)

# ---- pure date calculations ----


def test_days_before_fire_at_basic() -> None:
    next_charge_at = datetime.datetime(2026, 8, 10, 3, 0, tzinfo=datetime.UTC)
    result = calculate_days_before_fire_at(next_charge_at, "UTC")
    assert result == datetime.datetime(
        2026, 8, 10 - DAYS_BEFORE_N, REMINDER_LOCAL_HOUR, 0, tzinfo=datetime.UTC
    )


def test_days_before_fire_at_crosses_month_boundary() -> None:
    next_charge_at = datetime.datetime(2026, 3, 2, 0, 0, tzinfo=datetime.UTC)
    result = calculate_days_before_fire_at(next_charge_at, "UTC")
    assert result == datetime.datetime(2026, 2, 27, REMINDER_LOCAL_HOUR, 0, tzinfo=datetime.UTC)


def test_days_before_fire_at_never_at_night_regardless_of_charge_time() -> None:
    next_charge_at = datetime.datetime(2026, 8, 10, 1, 30, tzinfo=datetime.UTC)
    result = calculate_days_before_fire_at(next_charge_at, "UTC")
    assert result.hour == REMINDER_LOCAL_HOUR


def test_weekly_digest_fire_at_lands_on_monday_morning() -> None:
    some_date = datetime.date(2026, 8, 5)
    monday = some_date - datetime.timedelta(days=some_date.weekday())
    now = datetime.datetime.combine(monday, datetime.time(9, 0), tzinfo=datetime.UTC)

    result = calculate_weekly_digest_fire_at(now, "UTC")

    assert result.weekday() == 0
    assert result.hour == DIGEST_LOCAL_HOUR
    assert result > now


def test_weekly_digest_fire_at_pushes_to_next_week_if_slot_already_passed() -> None:
    some_date = datetime.date(2026, 8, 5)
    monday = some_date - datetime.timedelta(days=some_date.weekday())
    now = datetime.datetime.combine(
        monday, datetime.time(DIGEST_LOCAL_HOUR + 1, 0), tzinfo=datetime.UTC
    )

    result = calculate_weekly_digest_fire_at(now, "UTC")

    assert result.weekday() == 0
    assert (result - now).days >= 6


def test_monthly_report_handles_end_of_month() -> None:
    now = datetime.datetime(2026, 1, 31, 8, 0, tzinfo=datetime.UTC)
    result = calculate_monthly_report_fire_at(now, "UTC")
    assert (result.year, result.month, result.day) == (2026, 2, 1)


def test_monthly_report_handles_year_end_rollover() -> None:
    now = datetime.datetime(2026, 12, 15, 8, 0, tzinfo=datetime.UTC)
    result = calculate_monthly_report_fire_at(now, "UTC")
    assert (result.year, result.month, result.day) == (2027, 1, 1)


def test_monthly_report_handles_leap_year_february() -> None:
    now = datetime.datetime(2024, 2, 29, 8, 0, tzinfo=datetime.UTC)
    result = calculate_monthly_report_fire_at(now, "UTC")
    assert (result.year, result.month, result.day) == (2024, 3, 1)


# ---- ReminderService.recompute_for_user ----

_NOW = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)


async def test_recompute_off_clears_pending_reminders(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=850001, timezone="UTC", base_currency="USD")

    reminder_repo = ReminderRepository(session)
    await reminder_repo.upsert_pending(
        user_id=user.id,
        subscription_id=None,
        kind=ReminderPolicy.WEEKLY_DIGEST,
        fire_at=_NOW + datetime.timedelta(days=1),
    )

    user.reminder_policy = ReminderPolicy.OFF
    service = ReminderService(reminder_repo)
    await service.recompute_for_user(user, [], _NOW)

    assert (
        await reminder_repo.get_pending(
            user_id=user.id, subscription_id=None, kind=ReminderPolicy.WEEKLY_DIGEST
        )
        is None
    )


async def test_recompute_days_before_creates_one_reminder_per_active_subscription(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=850002, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.DAYS_BEFORE

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
        next_charge_at=datetime.datetime(2026, 8, 10, tzinfo=datetime.UTC),
    )

    reminder_repo = ReminderRepository(session)
    service = ReminderService(reminder_repo)
    await service.recompute_for_user(user, [subscription], _NOW)

    reminder = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=subscription.id, kind=ReminderPolicy.DAYS_BEFORE
    )
    assert reminder is not None
    assert reminder.fire_at == datetime.datetime(
        2026, 8, 7, REMINDER_LOCAL_HOUR, 0, tzinfo=datetime.UTC
    )


async def test_recompute_days_before_is_idempotent(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=850003, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.DAYS_BEFORE

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
        next_charge_at=datetime.datetime(2026, 8, 10, tzinfo=datetime.UTC),
    )

    reminder_repo = ReminderRepository(session)
    service = ReminderService(reminder_repo)
    await service.recompute_for_user(user, [subscription], _NOW)
    await service.recompute_for_user(user, [subscription], _NOW)

    result = await session.execute(
        select(Reminder).where(Reminder.subscription_id == subscription.id)
    )
    assert len(result.scalars().all()) == 1


async def test_recompute_days_before_removes_stale_reminder_for_cancelled_subscription(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=850004, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.DAYS_BEFORE

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
        next_charge_at=datetime.datetime(2026, 8, 10, tzinfo=datetime.UTC),
    )

    reminder_repo = ReminderRepository(session)
    service = ReminderService(reminder_repo)
    await service.recompute_for_user(user, [subscription], _NOW)

    subscription.status = SubscriptionStatus.CANCELLED
    await service.recompute_for_user(user, [subscription], _NOW)

    assert (
        await reminder_repo.get_pending(
            user_id=user.id, subscription_id=subscription.id, kind=ReminderPolicy.DAYS_BEFORE
        )
        is None
    )


async def test_recompute_weekly_digest_creates_single_user_level_reminder(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=850005, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.WEEKLY_DIGEST

    reminder_repo = ReminderRepository(session)
    service = ReminderService(reminder_repo)
    await service.recompute_for_user(user, [], _NOW)

    reminder = await reminder_repo.get_pending(
        user_id=user.id, subscription_id=None, kind=ReminderPolicy.WEEKLY_DIGEST
    )
    assert reminder is not None
    assert reminder.fire_at.weekday() == 0


async def test_recompute_switching_policy_clears_previous_kind(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=850006, timezone="UTC", base_currency="USD")
    user.reminder_policy = ReminderPolicy.WEEKLY_DIGEST

    reminder_repo = ReminderRepository(session)
    service = ReminderService(reminder_repo)
    await service.recompute_for_user(user, [], _NOW)

    user.reminder_policy = ReminderPolicy.MONTHLY_REPORT
    await service.recompute_for_user(user, [], _NOW)

    assert (
        await reminder_repo.get_pending(
            user_id=user.id, subscription_id=None, kind=ReminderPolicy.WEEKLY_DIGEST
        )
        is None
    )
    assert (
        await reminder_repo.get_pending(
            user_id=user.id, subscription_id=None, kind=ReminderPolicy.MONTHLY_REPORT
        )
        is not None
    )
