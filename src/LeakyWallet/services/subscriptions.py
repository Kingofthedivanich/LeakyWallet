import datetime
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from LeakyWallet.db.models.subscription import (
    Subscription,
    SubscriptionPeriod,
    SubscriptionSource,
    SubscriptionStatus,
)
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.utils.money import monthly_equivalent, yearly_equivalent


@dataclass(frozen=True)
class SubscriptionSummary:
    monthly_total: Decimal
    yearly_total: Decimal
    other_currencies: frozenset[str]


class SubscriptionService:
    def __init__(self, repository: SubscriptionRepository) -> None:
        self._repository = repository

    async def create(
        self,
        *,
        user_id: int,
        custom_name: str,
        amount: Decimal,
        currency: str,
        period: SubscriptionPeriod,
        next_charge_at: datetime.datetime,
    ) -> Subscription:
        return await self._repository.create(
            user_id=user_id,
            amount=amount,
            currency=currency,
            period=period,
            source=SubscriptionSource.MANUAL,
            custom_name=custom_name,
            next_charge_at=next_charge_at,
        )

    async def list_visible(self, user_id: int) -> Sequence[Subscription]:
        subscriptions = await self._repository.list_by_user(user_id)
        return [
            s for s in subscriptions if s.status != SubscriptionStatus.CANCELLED and s.is_recurring
        ]

    async def get_owned(self, subscription_id: int, user_id: int) -> Subscription | None:
        subscription = await self._repository.get_by_id(subscription_id)
        if subscription is None or subscription.user_id != user_id:
            return None
        return subscription

    async def update(
        self,
        subscription: Subscription,
        *,
        custom_name: str | None = None,
        amount: Decimal | None = None,
        currency: str | None = None,
        period: SubscriptionPeriod | None = None,
        next_charge_at: datetime.datetime | None = None,
    ) -> Subscription:
        if custom_name is not None:
            subscription.custom_name = custom_name
        if amount is not None:
            subscription.amount = amount
        if currency is not None:
            subscription.currency = currency
        if period is not None:
            subscription.period = period
        if next_charge_at is not None:
            subscription.next_charge_at = next_charge_at
        return subscription

    async def delete(self, subscription: Subscription) -> None:
        subscription.status = SubscriptionStatus.CANCELLED

    async def summary(self, user_id: int, base_currency: str) -> SubscriptionSummary:
        subscriptions = await self.list_visible(user_id)
        monthly_total = Decimal("0")
        yearly_total = Decimal("0")
        other_currencies: set[str] = set()

        for subscription in subscriptions:
            if subscription.currency != base_currency:
                other_currencies.add(subscription.currency)
                continue
            monthly_total += monthly_equivalent(subscription.amount, subscription.period)
            yearly_total += yearly_equivalent(subscription.amount, subscription.period)

        return SubscriptionSummary(
            monthly_total=monthly_total,
            yearly_total=yearly_total,
            other_currencies=frozenset(other_currencies),
        )
