from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from LeakyWallet.config import get_settings
from LeakyWallet.db import models  # noqa: F401  registers all mappers on Base.metadata
from LeakyWallet.db.base import Base


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    settings = get_settings()
    db_name = settings.database_url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database {db_name!r}: this fixture drops and "
            "recreates every table, and that name doesn't look like a test database (expected "
            "it to end in '_test'). Run via `make test`, or point DATABASE_URL at a *_test "
            "database explicitly - never at the dev/prod one."
        )

    test_engine = create_async_engine(settings.database_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        outer_transaction = await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with session_factory() as db_session:
            yield db_session
        await outer_transaction.rollback()


@pytest_asyncio.fixture
async def bot(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Bot]:
    fake_bot = Bot(
        token="123456:TEST-TOKEN", default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    monkeypatch.setattr(Bot, "__call__", AsyncMock(return_value=None))
    yield fake_bot
    await fake_bot.session.close()
