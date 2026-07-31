import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.email_account import EmailAccount, EmailProvider
from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.repositories.users import UserRepository


async def test_create_user_with_subscription_and_transaction(session: AsyncSession) -> None:
    users = UserRepository(session)
    subscriptions = SubscriptionRepository(session)
    transactions = TransactionRepository(session)

    user = await users.create(tg_id=123456789, timezone="Europe/Moscow", base_currency="RUB")

    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("299.00"),
        currency="RUB",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
    )

    transaction = await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC),
        amount=Decimal("299.00"),
        currency="RUB",
    )

    await session.commit()

    fetched_user = await users.get_by_tg_id(123456789)
    assert fetched_user is not None
    assert fetched_user.id == user.id
    assert fetched_user.base_currency == "RUB"

    fetched_subscriptions = await subscriptions.list_by_user(user.id)
    assert len(fetched_subscriptions) == 1
    assert fetched_subscriptions[0].id == subscription.id
    assert fetched_subscriptions[0].custom_name == "Netflix"

    fetched_transactions = await transactions.list_by_subscription(subscription.id)
    assert len(fetched_transactions) == 1
    assert fetched_transactions[0].id == transaction.id
    assert fetched_transactions[0].amount == Decimal("299.00")


async def test_transaction_dedup_by_message_id(session: AsyncSession) -> None:
    users = UserRepository(session)
    subscriptions = SubscriptionRepository(session)
    transactions = TransactionRepository(session)

    user = await users.create(tg_id=987654321, timezone="UTC", base_currency="USD")
    subscription = await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Spotify",
    )
    email_account = EmailAccount(
        user_id=user.id,
        provider=EmailProvider.GMAIL,
        email="user@gmail.com",
        encrypted_token="encrypted",
    )
    session.add(email_account)
    await session.flush()

    assert not await transactions.exists(email_account_id=email_account.id, message_id="msg-1")

    await transactions.create(
        subscription_id=subscription.id,
        charged_at=datetime.datetime(2026, 6, 1, tzinfo=datetime.UTC),
        amount=Decimal("9.99"),
        currency="USD",
        email_account_id=email_account.id,
        message_id="msg-1",
    )
    await session.flush()

    assert await transactions.exists(email_account_id=email_account.id, message_id="msg-1")
