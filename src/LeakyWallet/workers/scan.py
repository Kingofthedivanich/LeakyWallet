import datetime
from typing import Any

from aiogram import Bot

from LeakyWallet.bot import texts
from LeakyWallet.db.models.email_account import EmailAccountStatus
from LeakyWallet.logging import get_logger
from LeakyWallet.mail.gmail import SUBSCRIPTION_KEYWORDS, GmailClient, load_catalog_domains
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService

logger = get_logger(__name__)

PROGRESS_STEP = 25


async def scan_all_email_accounts(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        active_ids = await EmailAccountRepository(session).list_active_ids()

    for email_account_id in active_ids:
        await ctx["redis"].enqueue_job("scan_email_account", email_account_id)


async def scan_email_account(ctx: dict[str, Any], email_account_id: int) -> None:
    session_factory = ctx["session_factory"]
    bot: Bot | None = ctx.get("bot")

    async with session_factory() as session:
        email_repo = EmailAccountRepository(session)
        email_account = await email_repo.get_by_id(email_account_id)
        if email_account is None or email_account.status != EmailAccountStatus.ACTIVE:
            return

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(email_account.user_id)
        if user is None:
            return

        email_service = EmailAccountService(email_repo)
        try:
            access_token = await email_service.get_valid_access_token(email_account)
        except Exception:
            logger.exception("failed to obtain access token", email_account_id=email_account_id)
            email_account.status = EmailAccountStatus.ERROR
            await session.commit()
            return

        is_bootstrap = email_account.cursor is None
        if is_bootstrap and bot is not None:
            await bot.send_message(user.tg_id, texts.SCAN_STARTED)

        progress_state = {"last_reported": 0}

        async def report_progress(done: int, total: int) -> None:
            if bot is None:
                return
            if done - progress_state["last_reported"] < PROGRESS_STEP and done != total:
                return
            progress_state["last_reported"] = done
            await bot.send_message(user.tg_id, texts.SCAN_PROGRESS.format(done=done, total=total))

        client = GmailClient(
            access_token,
            catalog_domains=load_catalog_domains(),
            keywords=SUBSCRIPTION_KEYWORDS,
            on_progress=report_progress if is_bootstrap else None,
        )

        try:
            messages, new_cursor = await client.fetch_since(email_account.cursor)
        except Exception:
            logger.exception("scan failed", email_account_id=email_account_id)
            email_account.status = EmailAccountStatus.ERROR
            await session.commit()
            if bot is not None:
                await bot.send_message(user.tg_id, texts.SCAN_FAILED)
            return

        redis_pool = ctx["redis"]
        for message in messages:
            await redis_pool.enqueue_job(
                "parse_candidate",
                email_account_id,
                message.message_id,
                message.sender,
                message.subject,
                message.snippet,
                message.received_at.isoformat(),
            )

        email_account.cursor = new_cursor
        email_account.last_synced_at = datetime.datetime.now(datetime.UTC)
        await session.commit()

        if bot is not None:
            await bot.send_message(user.tg_id, texts.SCAN_DONE.format(count=len(messages)))
