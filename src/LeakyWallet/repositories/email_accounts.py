from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.email_account import EmailAccount, EmailAccountStatus, EmailProvider


class EmailAccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, email_account_id: int) -> EmailAccount | None:
        return await self._session.get(EmailAccount, email_account_id)

    async def get_by_user_and_provider(
        self, user_id: int, provider: EmailProvider
    ) -> EmailAccount | None:
        result = await self._session.execute(
            select(EmailAccount).where(
                EmailAccount.user_id == user_id, EmailAccount.provider == provider
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, *, user_id: int, provider: EmailProvider, email: str, encrypted_token: str
    ) -> EmailAccount:
        email_account = EmailAccount(
            user_id=user_id, provider=provider, email=email, encrypted_token=encrypted_token
        )
        self._session.add(email_account)
        await self._session.flush()
        return email_account

    async def delete(self, email_account: EmailAccount) -> None:
        await self._session.delete(email_account)

    async def list_active_ids(self) -> Sequence[int]:
        result = await self._session.execute(
            select(EmailAccount.id).where(EmailAccount.status == EmailAccountStatus.ACTIVE)
        )
        return result.scalars().all()
