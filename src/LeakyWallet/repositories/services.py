from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.service import Service


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_slug(self, slug: str) -> Service | None:
        result = await self._session.execute(select(Service).where(Service.slug == slug))
        return result.scalar_one_or_none()

    async def create(
        self, *, slug: str, name: str, domain_patterns: list[str], cancel_url: str | None
    ) -> Service:
        service = Service(
            slug=slug, name=name, domain_patterns=domain_patterns, cancel_url=cancel_url
        )
        self._session.add(service)
        await self._session.flush()
        return service
