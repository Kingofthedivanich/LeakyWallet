from typing import Any

from aiogram.types import TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot.middlewares.user_context import UserContextMiddleware
from LeakyWallet.repositories.users import UserRepository


async def test_user_context_middleware_creates_new_user(session: AsyncSession) -> None:
    middleware = UserContextMiddleware()
    tg_user = TgUser(id=333333, is_bot=False, first_name="Test")
    handled: dict[str, Any] = {}

    async def handler(event: TelegramObject, data: dict[str, Any]) -> str:
        handled.update(data)
        return "ok"

    data: dict[str, Any] = {"session": session, "event_from_user": tg_user}
    result = await middleware(handler, TelegramObject(), data)

    assert result == "ok"
    assert handled["user"].tg_id == tg_user.id

    users = UserRepository(session)
    fetched = await users.get_by_tg_id(tg_user.id)
    assert fetched is not None
    assert fetched.tg_id == tg_user.id


async def test_user_context_middleware_reuses_existing_user(session: AsyncSession) -> None:
    users = UserRepository(session)
    existing = await users.create(tg_id=444444, timezone="UTC", base_currency="USD")

    middleware = UserContextMiddleware()
    tg_user = TgUser(id=444444, is_bot=False, first_name="Test")

    async def handler(event: TelegramObject, data: dict[str, Any]) -> None:
        return None

    data: dict[str, Any] = {"session": session, "event_from_user": tg_user}
    await middleware(handler, TelegramObject(), data)

    assert data["user"].id == existing.id
