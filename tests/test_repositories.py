import datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.email_account import EmailAccount, EmailProvider
from LeakyWallet.db.models.service import ServiceCategory
from LeakyWallet.db.models.subscription import SubscriptionPeriod, SubscriptionSource
from LeakyWallet.repositories.services import ServiceRepository
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


async def test_service_get_or_create_is_idempotent(session: AsyncSession) -> None:
    services = ServiceRepository(session)

    first = await services.get_or_create(
        slug="race-test-service",
        name="Race Test Service",
        domain_patterns=["race-test.example"],
        cancel_url=None,
        category=ServiceCategory.OTHER,
    )
    second = await services.get_or_create(
        slug="race-test-service",
        name="Race Test Service",
        domain_patterns=["race-test.example"],
        cancel_url=None,
        category=ServiceCategory.OTHER,
    )

    assert first.id == second.id


async def test_service_slug_unique_constraint_rejects_bare_duplicate_insert(
    session: AsyncSession,
) -> None:
    # Regression guard for the get_or_create() savepoint/catch: this proves the
    # DB-level uniqueness the fix relies on is actually still enforced.
    services = ServiceRepository(session)
    await services.create(
        slug="dup-slug",
        name="First",
        domain_patterns=[],
        cancel_url=None,
    )
    with pytest.raises(IntegrityError):
        await services.create(
            slug="dup-slug",
            name="Second",
            domain_patterns=[],
            cancel_url=None,
        )


async def test_subscription_get_or_create_email_is_idempotent_by_service(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970501, timezone="UTC", base_currency="USD")
    services = ServiceRepository(session)
    service = await services.create(
        slug="idempotent-service", name="Idempotent Service", domain_patterns=[], cancel_url=None
    )

    subscriptions = SubscriptionRepository(session)
    first = await subscriptions.get_or_create_email(
        user_id=user.id,
        service_id=service.id,
        custom_name="Idempotent Service",
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=None,
    )
    second = await subscriptions.get_or_create_email(
        user_id=user.id,
        service_id=service.id,
        custom_name="Idempotent Service",
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=None,
    )

    assert first.id == second.id
    assert len(await subscriptions.list_by_user(user.id)) == 1


async def test_subscription_get_or_create_email_is_idempotent_by_custom_name(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=970502, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    first = await subscriptions.get_or_create_email(
        user_id=user.id,
        service_id=None,
        custom_name="Unmatched Sender",
        amount=Decimal("4.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=None,
    )
    second = await subscriptions.get_or_create_email(
        user_id=user.id,
        service_id=None,
        custom_name="Unmatched Sender",
        amount=Decimal("4.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        next_charge_at=None,
    )

    assert first.id == second.id
    assert len(await subscriptions.list_by_user(user.id)) == 1


async def test_email_subscription_custom_name_unique_constraint_rejects_bare_duplicate(
    session: AsyncSession,
) -> None:
    # The bug this guards against: two concurrent parse_candidate jobs for the
    # same unmatched sender both saw "no subscription yet" and both inserted,
    # silently duplicating it (get_by_user_and_custom_name has no DB backing).
    users = UserRepository(session)
    user = await users.create(tg_id=970503, timezone="UTC", base_currency="RUB")

    subscriptions = SubscriptionRepository(session)
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("3599.00"),
        currency="RUB",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.EMAIL,
        custom_name="Платформа ОФД",
    )
    with pytest.raises(IntegrityError):
        await subscriptions.create(
            user_id=user.id,
            amount=Decimal("3599.00"),
            currency="RUB",
            period=SubscriptionPeriod.MONTHLY,
            source=SubscriptionSource.EMAIL,
            custom_name="Платформа ОФД",
        )


async def test_manual_subscriptions_may_share_a_name(session: AsyncSession) -> None:
    # The unique index is scoped to source=email on purpose - two manually
    # added subscriptions with the same name (e.g. two family members' plans)
    # must stay legal.
    users = UserRepository(session)
    user = await users.create(tg_id=970504, timezone="UTC", base_currency="USD")

    subscriptions = SubscriptionRepository(session)
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
    )
    await subscriptions.create(
        user_id=user.id,
        amount=Decimal("9.99"),
        currency="USD",
        period=SubscriptionPeriod.MONTHLY,
        source=SubscriptionSource.MANUAL,
        custom_name="Netflix",
    )  # must not raise

    assert len(await subscriptions.list_by_user(user.id)) == 2
