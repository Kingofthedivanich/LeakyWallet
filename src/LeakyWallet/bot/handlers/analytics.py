import datetime

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.bot import texts
from LeakyWallet.bot.keyboards import MENU_ANALYTICS
from LeakyWallet.db.models.user import User
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.services.analytics import AnalyticsService

router = Router(name="analytics")


@router.callback_query(F.data == MENU_ANALYTICS)
async def open_analytics(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    assert isinstance(callback.message, Message)

    service = AnalyticsService(
        SubscriptionRepository(session), TransactionRepository(session), ServiceRepository(session)
    )
    now = datetime.datetime.now(datetime.UTC)

    top_spending = await service.top_spending(user.id, user.base_currency)
    category_breakdown = await service.category_breakdown(user.id, user.base_currency)
    trend = await service.monthly_trend(user.id, user.base_currency, now=now)
    dormant = await service.find_dormant(user.id, now)

    text = texts.format_analytics_overview(
        top_spending=top_spending,
        category_breakdown=category_breakdown,
        trend=trend,
        dormant=dormant,
        base_currency=user.base_currency,
    )
    await callback.message.answer(text)
    await callback.answer()
