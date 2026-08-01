import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.export import CSV_HEADER, transactions_to_csv


def test_transactions_to_csv_empty_list_returns_only_header() -> None:
    csv_text = transactions_to_csv([])
    lines = csv_text.strip().splitlines()
    assert lines == [",".join(CSV_HEADER)]


async def test_transactions_to_csv_includes_subscription_name_and_amount(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970201, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Spotify",
    )

    transactions = TransactionRepository(session)
    await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
    )

    fetched = await transactions.list_by_user(user.id)
    csv_text = transactions_to_csv(fetched)

    lines = csv_text.strip().splitlines()
    assert lines[0] == ",".join(CSV_HEADER)
    assert "Spotify" in lines[1]
    assert "9.99" in lines[1]
    assert "USD" in lines[1]
