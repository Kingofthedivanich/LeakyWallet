import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.service import ServiceCategory
from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.analytics import AnalyticsService


async def _make_service(session: AsyncSession) -> AnalyticsService:
    return AnalyticsService(
        SubscriptionRepository(session), TransactionRepository(session), ServiceRepository(session)
    )


async def test_top_spending_orders_by_monthly_amount_descending(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970101, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("5.00"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Cheap",
    )
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("120.00"),
        currency="USD",
        period=SubscriptionPeriod.YEARLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Expensive yearly",
    )

    analytics = await _make_service(session)
    top = await analytics.top_spending(user.id, "USD")

    assert [item.subscription.custom_name for item in top] == ["Expensive yearly", "Cheap"]
    assert top[0].monthly_amount == Decimal("10.00")


async def test_top_spending_excludes_other_currencies(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970102, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("999.00"),
        currency="EUR",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Euro sub",
    )

    analytics = await _make_service(session)
    top = await analytics.top_spending(user.id, "USD")

    assert top == []


async def test_category_breakdown_groups_by_service_and_falls_back_to_other(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970103, timezone="UTC", base_currency="USD")

    services = ServiceRepository(session)
    streaming_service = await services.create(
        slug="test-streaming",
        name="Test Streaming",
        domain_patterns=["teststreaming.example"],
        cancel_url=None,
        category=ServiceCategory.STREAMING,
    )

    subscriptions = SubscriptionRepository(session)
    await subscriptions.create(
        user_id=user.id,
        service_id=streaming_service.id,
        amount=Decimal("10.00"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
    )
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("20.00"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="No catalog match",
    )

    analytics = await _make_service(session)
    breakdown = await analytics.category_breakdown(user.id, "USD")

    totals = {item.category: item.monthly_amount for item in breakdown}
    assert totals[ServiceCategory.STREAMING] == Decimal("10.00")
    assert totals[ServiceCategory.OTHER] == Decimal("20.00")


async def test_monthly_trend_sums_transactions_per_month(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970104, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Trend sub",
    )

    transactions = TransactionRepository(session)
    await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 6, 15, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
    )
    await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 7, 15, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
    )
    await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 7, 20, tzinfo=datetime.UTC),
        amount=Decimal("5.00"),
        currency="EUR",  # different currency - must not be summed into the USD trend
    )

    analytics = await _make_service(session)
    now = datetime.datetime(2026, 7, 31, tzinfo=datetime.UTC)
    trend = await analytics.monthly_trend(user.id, "USD", now=now, months=3)

    assert [point.month for point in trend] == ["2026-05", "2026-06", "2026-07"]
    by_month = {point.month: point.total for point in trend}
    assert by_month["2026-05"] == Decimal("0")
    assert by_month["2026-06"] == Decimal("9.99")
    assert by_month["2026-07"] == Decimal("9.99")


async def test_find_dormant_flags_email_subscription_with_stale_receipts(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970105, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Dormant sub",
    )

    transactions = TransactionRepository(session)
    await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
    )

    analytics = await _make_service(session)
    now = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)  # ~6 months of silence
    dormant = await analytics.find_dormant(user.id, now)

    assert [s.id for s in dormant] == [subscription.id]


async def test_find_dormant_ignores_recently_charged_and_manual_subscriptions(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970106, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    fresh = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Fresh sub",
    )
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Manual sub, never had receipts",
    )

    transactions = TransactionRepository(session)
    await transactions.create(
        subscription_id=fresh.id,
        charged_at=datetime.datetime(2026, 6, 25, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
    )

    analytics = await _make_service(session)
    now = datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
    dormant = await analytics.find_dormant(user.id, now)

    assert dormant == []


async def test_one_off_spending_groups_irregular_subscriptions_by_category(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970107, timezone="UTC", base_currency="RUB")

    services = ServiceRepository(session)
    gaming_service = await services.create(
        slug="test-gaming-store",
        name="Test Gaming Store",
        domain_patterns=["testgamingstore.example"],
        cancel_url=None,
        category=ServiceCategory.GAMING,
    )

    subscriptions = SubscriptionRepository(session)
    recurring = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("299.00"),
        currency="RUB",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Real subscription",
    )
    irregular = await subscriptions.create(
        user_id=user.id,
        service_id=gaming_service.id,
        amount=Decimal("100.00"),
        currency="RUB",
        period=SubscriptionPeriod.WEEKLY,
        source=SubscriptionSource.EMAIL,
    )
    irregular.is_recurring = False
    await session.flush()

    transactions = TransactionRepository(session)
    await transactions.create(
        subscription_id=recurring.id,
        charged_at=datetime.datetime(2026, 6, 1, tzinfo=datetime.UTC),
        amount=Decimal("299.00"),
        currency="RUB",
    )
    await transactions.create(
        subscription_id=irregular.id,
        charged_at=datetime.datetime(2026, 6, 1, tzinfo=datetime.UTC),
        amount=Decimal("100.00"),
        currency="RUB",
    )
    await transactions.create(
        subscription_id=irregular.id,
        charged_at=datetime.datetime(2026, 6, 5, tzinfo=datetime.UTC),
        amount=Decimal("250.00"),
        currency="RUB",
    )

    analytics = await _make_service(session)
    one_off = await analytics.one_off_spending(user.id, "RUB")

    assert len(one_off) == 1
    assert one_off[0].category == ServiceCategory.GAMING
    assert one_off[0].total_amount == Decimal("350.00")
    assert one_off[0].transaction_count == 2
