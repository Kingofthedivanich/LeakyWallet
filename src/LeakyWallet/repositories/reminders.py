import datetime
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.reminder import Reminder
from LeakyWallet.db.models.user import ReminderPolicy


class ReminderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_pending(
        self, *, user_id: int, subscription_id: int | None, kind: ReminderPolicy
    ) -> Reminder | None:
        result = await self._session.execute(
            select(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.subscription_id == subscription_id,
                Reminder.kind == kind,
                Reminder.sent_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def upsert_pending(
        self,
        *,
        user_id: int,
        subscription_id: int | None,
        kind: ReminderPolicy,
        fire_at: datetime.datetime,
    ) -> Reminder:
        existing = await self.get_pending(
            user_id=user_id, subscription_id=subscription_id, kind=kind
        )
        if existing is not None:
            existing.fire_at = fire_at
            return existing

        reminder = Reminder(
            user_id=user_id, subscription_id=subscription_id, kind=kind, fire_at=fire_at
        )
        self._session.add(reminder)
        await self._session.flush()
        return reminder

    async def delete_pending_for_user(
        self, user_id: int, kinds: set[ReminderPolicy] | None = None
    ) -> None:
        stmt = delete(Reminder).where(Reminder.user_id == user_id, Reminder.sent_at.is_(None))
        if kinds is not None:
            stmt = stmt.where(Reminder.kind.in_(kinds))
        await self._session.execute(stmt)

    async def delete_stale_days_before(self, user_id: int, keep_subscription_ids: set[int]) -> None:
        stmt = delete(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.kind == ReminderPolicy.DAYS_BEFORE,
            Reminder.sent_at.is_(None),
        )
        if keep_subscription_ids:
            stmt = stmt.where(Reminder.subscription_id.not_in(keep_subscription_ids))
        await self._session.execute(stmt)

    async def list_due(self, now: datetime.datetime) -> Sequence[Reminder]:
        result = await self._session.execute(
            select(Reminder).where(Reminder.fire_at <= now, Reminder.sent_at.is_(None))
        )
        return result.scalars().all()

    async def mark_sent(self, reminder: Reminder, sent_at: datetime.datetime) -> None:
        reminder.sent_at = sent_at
