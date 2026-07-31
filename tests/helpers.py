from sqlalchemy.ext.asyncio import AsyncSession


class SessionFactory:
    """Wraps the test's transactional session so worker jobs reuse it instead of
    opening a real connection - keeps the test isolated via the session fixture's
    outer rollback."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> "SessionFactory":
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *exc_info: object) -> None:
        return None
