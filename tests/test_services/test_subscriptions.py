import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionStatus
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.subscriptions import SubscriptionService

_NEXT_CHARGE = datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC)


async def test_create_and_get_owned(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900001, timezone="UTC", base_currency="USD")
    other_user = await users.create(tg_id=900002, timezone="UTC", base_currency="USD")

    service = SubscriptionService(SubscriptionRepository(session))
    subscription = await service.create(
        user_id=user.id,
        custom_name="Netflix",
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )

    fetched = await service.get_owned(subscription.id, user.id)
    assert fetched is not None
    assert fetched.custom_name == "Netflix"
    assert fetched.next_charge_at == _NEXT_CHARGE

    assert await service.get_owned(subscription.id, other_user.id) is None


async def test_list_visible_excludes_cancelled(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900003, timezone="UTC", base_currency="USD")
    service = SubscriptionService(SubscriptionRepository(session))

    active = await service.create(
        user_id=user.id,
        custom_name="Spotify",
        amount=Decimal("5.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )
    cancelled = await service.create(
        user_id=user.id,
        custom_name="Old thing",
        amount=Decimal("1.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )
    await service.delete(cancelled)

    visible_ids = {s.id for s in await service.list_visible(user.id)}
    assert active.id in visible_ids
    assert cancelled.id not in visible_ids
    assert cancelled.status == SubscriptionStatus.CANCELLED


async def test_update_changes_fields(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900004, timezone="UTC", base_currency="USD")
    service = SubscriptionService(SubscriptionRepository(session))

    subscription = await service.create(
        user_id=user.id,
        custom_name="Netflix",
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )

    await service.update(subscription, amount=Decimal("12.99"), currency="EUR")
    assert subscription.amount == Decimal("12.99")
    assert subscription.currency == "EUR"

    await service.update(subscription, period=SubscriptionPeriod.YEARLY, custom_name="Netflix Pro")
    assert subscription.period == SubscriptionPeriod.YEARLY
    assert subscription.custom_name == "Netflix Pro"


async def test_summary_sums_only_base_currency(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900005, timezone="UTC", base_currency="USD")
    service = SubscriptionService(SubscriptionRepository(session))

    await service.create(
        user_id=user.id,
        custom_name="Netflix",
        amount=Decimal("10.00"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )
    await service.create(
        user_id=user.id,
        custom_name="Yearly thing",
        amount=Decimal("120.00"),
        currency="USD",
        period=SubscriptionPeriod.YEARLY,
        next_charge_at=_NEXT_CHARGE,
    )
    await service.create(
        user_id=user.id,
        custom_name="Foreign",
        amount=Decimal("5.00"),
        currency="EUR",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=_NEXT_CHARGE,
    )

    summary = await service.summary(user.id, "USD")
    assert summary.monthly_total == Decimal("20.00")
    assert summary.yearly_total == Decimal("240.00")
    assert summary.other_currencies == frozenset({"EUR"})
