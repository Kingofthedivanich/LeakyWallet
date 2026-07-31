import datetime
from typing import Any

from aiogram import Bot

from LeakyWallet.bot import texts
from LeakyWallet.db.models.user import ReminderPolicy
from LeakyWallet.logging import get_logger
from LeakyWallet.repositories.reminders import ReminderRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.reminders import ReminderService
from LeakyWallet.services.subscriptions import SubscriptionService

logger = get_logger(__name__)


async def recompute_reminders(ctx: dict[str, Any]) -> None:
    session_factory = ctx["session_factory"]
    now = datetime.datetime.now(datetime.UTC)

    async with session_factory() as session:
        users = UserRepository(session)
        subscriptions_repo = SubscriptionRepository(session)
        subscription_service = SubscriptionService(subscriptions_repo)
        reminder_service = ReminderService(ReminderRepository(session))

        for user in await users.list_with_reminders_enabled():
            subscriptions = await subscription_service.list_visible(user.id)
            await reminder_service.recompute_for_user(user, subscriptions, now)

        await session.commit()


async def send_due_reminders(ctx: dict[str, Any]) -> None:
    bot: Bot | None = ctx.get("bot")
    if bot is None:
        return

    session_factory = ctx["session_factory"]
    now = datetime.datetime.now(datetime.UTC)

    async with session_factory() as session:
        reminder_repo = ReminderRepository(session)
        subscription_repo = SubscriptionRepository(session)
        subscription_service = SubscriptionService(subscription_repo)
        user_repo = UserRepository(session)

        for reminder in await reminder_repo.list_due(now):
            user = await user_repo.get_by_id(reminder.user_id)
            if user is None:
                continue

            try:
                if reminder.kind == ReminderPolicy.DAYS_BEFORE:
                    subscription = (
                        await subscription_repo.get_by_id(reminder.subscription_id)
                        if reminder.subscription_id is not None
                        else None
                    )
                    if subscription is None:
                        continue
                    text = texts.format_days_before_reminder(subscription, user.timezone)
                else:
                    subscriptions = await subscription_service.list_visible(user.id)
                    summary = await subscription_service.summary(user.id, user.base_currency)
                    header = (
                        texts.WEEKLY_DIGEST_HEADER
                        if reminder.kind == ReminderPolicy.WEEKLY_DIGEST
                        else texts.MONTHLY_REPORT_HEADER
                    )
                    text = texts.format_subscriptions_list(
                        subscriptions, summary, user.base_currency, title=header
                    )

                await bot.send_message(user.tg_id, text)
            except Exception:
                logger.exception("failed to send reminder", reminder_id=reminder.id)
                continue

            await reminder_repo.mark_sent(reminder, now)
            await session.flush()

        await session.commit()
