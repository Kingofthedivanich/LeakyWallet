import datetime
from dataclasses import dataclass
from decimal import Decimal

from LeakyWallet.db.models.service import ServiceCategory
from LeakyWallet.db.models.subscription import Subscription, SubscriptionSource, SubscriptionStatus
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.utils.dates import add_period
from LeakyWallet.utils.money import monthly_equivalent

DORMANT_GRACE_PERIODS = 2


@dataclass(frozen=True)
class SpendingItem:
    subscription: Subscription
    monthly_amount: Decimal


@dataclass(frozen=True)
class CategoryTotal:
    category: ServiceCategory
    monthly_amount: Decimal


@dataclass(frozen=True)
class MonthPoint:
    month: str  # "YYYY-MM"
    total: Decimal


class AnalyticsService:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        transactions: TransactionRepository,
        services: ServiceRepository,
    ) -> None:
        self._subscriptions = subscriptions
        self._transactions = transactions
        self._services = services

    async def _active_in_base_currency(
        self, user_id: int, base_currency: str
    ) -> list[Subscription]:
        subscriptions = await self._subscriptions.list_by_user(user_id)
        return [
            s
            for s in subscriptions
            if s.status == SubscriptionStatus.ACTIVE and s.currency == base_currency
        ]

    async def top_spending(
        self, user_id: int, base_currency: str, *, limit: int = 5
    ) -> list[SpendingItem]:
        subscriptions = await self._active_in_base_currency(user_id, base_currency)
        items = [
            SpendingItem(subscription=s, monthly_amount=monthly_equivalent(s.amount, s.period))
            for s in subscriptions
        ]
        items.sort(key=lambda item: item.monthly_amount, reverse=True)
        return items[:limit]

    async def category_breakdown(self, user_id: int, base_currency: str) -> list[CategoryTotal]:
        subscriptions = await self._active_in_base_currency(user_id, base_currency)
        service_ids = {s.service_id for s in subscriptions if s.service_id is not None}
        services = await self._services.list_by_ids(list(service_ids))
        category_by_service_id = {service.id: service.category for service in services}

        totals: dict[ServiceCategory, Decimal] = {}
        for subscription in subscriptions:
            category = ServiceCategory.OTHER
            if subscription.service_id is not None:
                category = category_by_service_id.get(
                    subscription.service_id, ServiceCategory.OTHER
                )
            totals[category] = totals.get(category, Decimal("0")) + monthly_equivalent(
                subscription.amount, subscription.period
            )

        breakdown = [CategoryTotal(category=c, monthly_amount=a) for c, a in totals.items()]
        breakdown.sort(key=lambda item: item.monthly_amount, reverse=True)
        return breakdown

    async def monthly_trend(
        self, user_id: int, base_currency: str, *, now: datetime.datetime, months: int = 6
    ) -> list[MonthPoint]:
        month_keys = []
        year, month = now.year, now.month
        for _ in range(months):
            month_keys.append(f"{year:04d}-{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        month_keys.reverse()

        cutoff = datetime.datetime(*_year_month_from_key(month_keys[0]), 1, tzinfo=datetime.UTC)
        transactions = await self._transactions.list_by_user(user_id, since=cutoff)

        totals: dict[str, Decimal] = dict.fromkeys(month_keys, Decimal("0"))
        for transaction in transactions:
            if transaction.currency != base_currency:
                continue
            key = f"{transaction.charged_at.year:04d}-{transaction.charged_at.month:02d}"
            if key in totals:
                totals[key] += transaction.amount

        return [MonthPoint(month=key, total=totals[key]) for key in month_keys]

    async def find_dormant(self, user_id: int, now: datetime.datetime) -> list[Subscription]:
        subscriptions = await self._subscriptions.list_by_user(user_id)
        dormant = []
        for subscription in subscriptions:
            if (
                subscription.status != SubscriptionStatus.ACTIVE
                or subscription.source != SubscriptionSource.EMAIL
            ):
                continue

            transactions = await self._transactions.list_by_subscription(subscription.id)
            if not transactions:
                continue

            last_charge = transactions[-1].charged_at
            expected_by = last_charge
            for _ in range(DORMANT_GRACE_PERIODS):
                expected_by = add_period(expected_by, subscription.period)

            if now > expected_by:
                dormant.append(subscription)

        return dormant


def _year_month_from_key(key: str) -> tuple[int, int]:
    year_str, month_str = key.split("-")
    return int(year_str), int(month_str)
