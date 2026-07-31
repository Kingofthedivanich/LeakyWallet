import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from LeakyWallet.bot import texts
from LeakyWallet.bot.dispatcher import create_dispatcher
from LeakyWallet.config import get_settings
from LeakyWallet.db.session import async_session_factory
from LeakyWallet.logging import configure_logging, get_logger
from LeakyWallet.mail import gmail, oauth
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService

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
arq_pool: ArqRedis | None = None


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _polling_task, arq_pool

    arq_pool = await create_pool(RedisSettings.from_dsn(str(settings.redis_url)))

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
    if arq_pool is not None:
        await arq_pool.close()


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


@app.get("/oauth/callback")
async def oauth_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
) -> HTMLResponse:
    if error is not None:
        return HTMLResponse(texts.EMAIL_CALLBACK_ERROR_HTML.format(detail=error), status_code=400)
    if code is None or state is None:
        return HTMLResponse(
            texts.EMAIL_CALLBACK_ERROR_HTML.format(detail="missing code or state"),
            status_code=400,
        )

    user_id = await oauth.pop_user_id_for_state(state)
    if user_id is None:
        return HTMLResponse(texts.EMAIL_CALLBACK_EXPIRED_HTML, status_code=400)

    try:
        tokens = await oauth.exchange_code_for_tokens(code)
        email = await gmail.get_profile_email(tokens.access_token)
    except Exception:
        logger.exception("oauth token exchange failed", user_id=user_id)
        return HTMLResponse(
            texts.EMAIL_CALLBACK_ERROR_HTML.format(detail="Google API error"), status_code=502
        )

    async with async_session_factory() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(user_id)
        if user is None:
            return HTMLResponse(
                texts.EMAIL_CALLBACK_ERROR_HTML.format(detail="unknown user"), status_code=404
            )

        service = EmailAccountService(EmailAccountRepository(session))
        email_account = await service.connect(user_id=user.id, email=email, tokens=tokens)
        await session.commit()

        tg_id = user.tg_id
        email_account_id = email_account.id

    if arq_pool is not None:
        await arq_pool.enqueue_job("scan_email_account", email_account_id)

    if bot is not None:
        await bot.send_message(tg_id, texts.EMAIL_CONNECTED_DM.format(email=email))

    return HTMLResponse(texts.EMAIL_CALLBACK_SUCCESS_HTML)
