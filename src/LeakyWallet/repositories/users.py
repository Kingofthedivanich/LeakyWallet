from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.user import ReminderPolicy, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()

    async def create(self, *, tg_id: int, timezone: str, base_currency: str) -> User:
        user = User(tg_id=tg_id, timezone=timezone, base_currency=base_currency)
        self._session.add(user)
        await self._session.flush()
        return user

    async def list_with_reminders_enabled(self) -> Sequence[User]:
        result = await self._session.execute(
            select(User).where(User.reminder_policy != ReminderPolicy.OFF)
        )
        return result.scalars().all()

    async def delete(self, user: User) -> None:
        await self._session.delete(user)
