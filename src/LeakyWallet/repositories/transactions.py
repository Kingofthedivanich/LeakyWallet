import datetime
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.transaction import Transaction


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_subscription(self, subscription_id: int) -> Sequence[Transaction]:
        result = await self._session.execute(
            select(Transaction)
            .where(Transaction.subscription_id == subscription_id)
            .order_by(Transaction.charged_at)
        )
        return result.scalars().all()

    async def exists(self, *, email_account_id: int, message_id: str) -> bool:
        result = await self._session.execute(
            select(Transaction.id).where(
                Transaction.email_account_id == email_account_id,
                Transaction.message_id == message_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        *,
        subscription_id: int,
        charged_at: datetime.datetime,
        amount: Decimal,
        currency: str,
        email_account_id: int | None = None,
        message_id: str | None = None,
    ) -> Transaction:
        transaction = Transaction(
            subscription_id=subscription_id,
            email_account_id=email_account_id,
            message_id=message_id,
            charged_at=charged_at,
            amount=amount,
            currency=currency,
        )
        self._session.add(transaction)
        await self._session.flush()
        return transaction
