import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, HTTPException, Request

from LeakyWallet.bot.dispatcher import create_dispatcher
from LeakyWallet.config import get_settings
from LeakyWallet.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

settings = get_settings()
bot = (
    Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    if settings.telegram_bot_token
    else None
)
dispatcher = create_dispatcher()

_polling_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _polling_task

    if bot is not None:
        if settings.telegram_use_webhook and settings.telegram_webhook_url:
            await bot.set_webhook(
                url=settings.telegram_webhook_url,
                secret_token=settings.telegram_webhook_secret,
            )
            logger.info("telegram webhook configured", url=settings.telegram_webhook_url)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            _polling_task = asyncio.create_task(dispatcher.start_polling(bot))
            logger.info("telegram bot started in polling mode")

    yield

    if _polling_task is not None:
        _polling_task.cancel()
    if bot is not None:
        await bot.session.close()


app = FastAPI(title="LeakyWallet", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook")
async def telegram_webhook(request: Request) -> dict[str, str]:
    if bot is None:
        raise HTTPException(status_code=503, detail="bot is not configured")

    if settings.telegram_webhook_secret:
        header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header != settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="invalid secret token")

    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dispatcher.feed_update(bot, update)
    return {"status": "ok"}
