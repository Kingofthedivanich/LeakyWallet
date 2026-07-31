from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from LeakyWallet.bot.handlers import email_connect, manual_add, settings, start, subscriptions
from LeakyWallet.bot.middlewares.db_session import DbSessionMiddleware
from LeakyWallet.bot.middlewares.user_context import UserContextMiddleware


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.update.outer_middleware(DbSessionMiddleware())
    dispatcher.update.outer_middleware(UserContextMiddleware())
    dispatcher.include_router(subscriptions.router)
    dispatcher.include_router(manual_add.router)
    dispatcher.include_router(settings.router)
    dispatcher.include_router(email_connect.router)
    dispatcher.include_router(start.router)
    return dispatcher
