from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.service import Service, ServiceCategory


class ServiceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, service_id: int) -> Service | None:
        return await self._session.get(Service, service_id)

    async def get_by_slug(self, slug: str) -> Service | None:
        result = await self._session.execute(select(Service).where(Service.slug == slug))
        return result.scalar_one_or_none()

    async def list_by_ids(self, service_ids: Sequence[int]) -> Sequence[Service]:
        if not service_ids:
            return []
        result = await self._session.execute(select(Service).where(Service.id.in_(service_ids)))
        return result.scalars().all()

    async def create(
        self,
        *,
        slug: str,
        name: str,
        domain_patterns: list[str],
        cancel_url: str | None,
        category: ServiceCategory = ServiceCategory.OTHER,
    ) -> Service:
        service = Service(
            slug=slug,
            name=name,
            domain_patterns=domain_patterns,
            cancel_url=cancel_url,
            category=category,
        )
        self._session.add(service)
        await self._session.flush()
        return service

    async def get_or_create(
        self,
        *,
        slug: str,
        name: str,
        domain_patterns: list[str],
        cancel_url: str | None,
        category: ServiceCategory = ServiceCategory.OTHER,
    ) -> Service:
        existing = await self.get_by_slug(slug)
        if existing is not None:
            return existing

        # Two concurrent parse_candidate jobs can both see "no such service"
        # and both try to create it - the loser hits the unique constraint on
        # slug. A savepoint contains that failure to just this insert so the
        # rest of the job's transaction isn't poisoned, then we re-read the
        # row the winner committed.
        try:
            async with self._session.begin_nested():
                service = Service(
                    slug=slug,
                    name=name,
                    domain_patterns=domain_patterns,
                    cancel_url=cancel_url,
                    category=category,
                )
                self._session.add(service)
                await self._session.flush()
        except IntegrityError:
            winner = await self.get_by_slug(slug)
            if winner is None:
                raise
            return winner
        return service
