from typing import Any

import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from arq.connections import RedisSettings
from arq.cron import cron

from LeakyWallet.config import get_settings
from LeakyWallet.db.session import async_session_factory
from LeakyWallet.logging import configure_logging
from LeakyWallet.sentry import init_sentry
from LeakyWallet.workers.notify import recompute_reminders, send_due_reminders
from LeakyWallet.workers.parse import parse_candidate
from LeakyWallet.workers.scan import scan_all_email_accounts, scan_email_account

configure_logging()
init_sentry()
settings = get_settings()

_EVERY_FIVE_MINUTES = set(range(0, 60, 5))
_EVERY_FIFTEEN_MINUTES = {0, 15, 30, 45}
_HEALTH_CHECK_INTERVAL_SECONDS = 20


async def healthcheck(ctx: dict[str, Any]) -> str:
    return "ok"


async def startup(ctx: dict[str, Any]) -> None:
    ctx["session_factory"] = async_session_factory
    ctx["bot"] = (
        Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        if settings.telegram_bot_token
        else None
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    bot: Bot | None = ctx.get("bot")
    if bot is not None:
        await bot.session.close()


async def on_job_start(ctx: dict[str, Any]) -> None:
    structlog.contextvars.bind_contextvars(job_id=ctx["job_id"])


async def on_job_end(ctx: dict[str, Any]) -> None:
    structlog.contextvars.clear_contextvars()


class WorkerSettings:
    functions = [
        healthcheck,
        recompute_reminders,
        send_due_reminders,
        scan_email_account,
        scan_all_email_accounts,
        parse_candidate,
    ]
    cron_jobs = [
        cron(recompute_reminders, minute=0),
        cron(send_due_reminders, minute=_EVERY_FIVE_MINUTES),
        cron(scan_all_email_accounts, minute=_EVERY_FIFTEEN_MINUTES),
    ]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end
    health_check_interval = _HEALTH_CHECK_INTERVAL_SECONDS
