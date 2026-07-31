import datetime
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.subscription import (
    Subscription,
    SubscriptionPeriod,
    SubscriptionSource,
    SubscriptionStatus,
)


class SubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, subscription_id: int) -> Subscription | None:
        return await self._session.get(Subscription, subscription_id)

    async def list_by_user(self, user_id: int) -> Sequence[Subscription]:
        result = await self._session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at)
        )
        return result.scalars().all()

    async def get_by_user_and_service(self, user_id: int, service_id: int) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id, Subscription.service_id == service_id
            )
        )
        return result.scalars().first()

    async def get_by_user_and_custom_name(
        self, user_id: int, custom_name: str
    ) -> Subscription | None:
        result = await self._session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.custom_name == custom_name,
                Subscription.service_id.is_(None),
            )
        )
        return result.scalars().first()

    async def create(
        self,
        *,
        user_id: int,
        amount: Decimal,
        currency: str,
        period: SubscriptionPeriod,
        source: SubscriptionSource,
        service_id: int | None = None,
        custom_name: str | None = None,
        next_charge_at: datetime.datetime | None = None,
    ) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            service_id=service_id,
            custom_name=custom_name,
            amount=amount,
            currency=currency,
            period=period,
            status=SubscriptionStatus.ACTIVE,
            source=source,
            next_charge_at=next_charge_at,
        )
        self._session.add(subscription)
        await self._session.flush()
        return subscription
