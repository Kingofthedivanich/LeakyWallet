from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from LeakyWallet.repositories.users import UserRepository


class UserContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return await handler(event, data)

        users = UserRepository(data["session"])
        user = await users.get_by_tg_id(telegram_user.id)
        if user is None:
            user = await users.create(tg_id=telegram_user.id, timezone="UTC", base_currency="USD")

        data["user"] = user
        return await handler(event, data)
