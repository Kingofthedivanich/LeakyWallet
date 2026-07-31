import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.subscription import Subscription, SubscriptionPeriod, SubscriptionSource
from LeakyWallet.db.models.transaction import Transaction
from LeakyWallet.mail.oauth import TokenResponse
from LeakyWallet.parsing.schemas import ParsedReceipt
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService
from LeakyWallet.services.receipts import ReceiptService


def _receipt(
    *,
    amount: str,
    currency: str = "RUB",
    charged_at: datetime.datetime,
    period: SubscriptionPeriod | None = None,
    sender_name: str = "Netflix",
    service_slug: str | None = "netflix",
) -> ParsedReceipt:
    return ParsedReceipt(
        amount=Decimal(amount),
        currency=currency,
        charged_at=charged_at,
        period=period,
        sender_name=sender_name,
        service_slug=service_slug,
        service_name="Netflix" if service_slug else None,
    )


async def _make_receipt_service(session: AsyncSession) -> ReceiptService:
    return ReceiptService(
        SubscriptionRepository(session),
        TransactionRepository(session),
        ServiceRepository(session),
    )


async def _make_email_account(session: AsyncSession, tg_id: int) -> tuple[int, int]:
    users = UserRepository(session)
    user = await users.create(tg_id=tg_id, timezone="UTC", base_currency="RUB")
    email_service = EmailAccountService(EmailAccountRepository(session))
    account = await email_service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )
    return user.id, account.id


async def test_record_receipt_creates_subscription_and_transaction(
    session: AsyncSession,
) -> None:
    user_id, email_account_id = await _make_email_account(session, 970001)
    service = await _make_receipt_service(session)

    receipt = _receipt(
        amount="799.00", charged_at=datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC)
    )
    transaction = await service.record_receipt(
        user_id=user_id, email_account_id=email_account_id, message_id="msg-1", receipt=receipt
    )

    assert transaction is not None
    assert transaction.amount == Decimal("799.00")

    result = await session.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscriptions = result.scalars().all()
    assert len(subscriptions) == 1
    assert subscriptions[0].source == SubscriptionSource.EMAIL
    assert subscriptions[0].custom_name == "Netflix"


async def test_record_receipt_is_idempotent_on_rerun(session: AsyncSession) -> None:
    user_id, email_account_id = await _make_email_account(session, 970002)
    service = await _make_receipt_service(session)

    receipt = _receipt(
        amount="799.00", charged_at=datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC)
    )

    first = await service.record_receipt(
        user_id=user_id, email_account_id=email_account_id, message_id="msg-2", receipt=receipt
    )
    second = await service.record_receipt(
        user_id=user_id, email_account_id=email_account_id, message_id="msg-2", receipt=receipt
    )

    assert first is not None
    assert second is None  # re-run of the same message_id must not duplicate

    result = await session.execute(
        select(Transaction).where(Transaction.email_account_id == email_account_id)
    )
    assert len(result.scalars().all()) == 1


async def test_record_receipt_reuses_subscription_for_repeat_charges(
    session: AsyncSession,
) -> None:
    user_id, email_account_id = await _make_email_account(session, 970003)
    service = await _make_receipt_service(session)

    first = await service.record_receipt(
        user_id=user_id,
        email_account_id=email_account_id,
        message_id="msg-3a",
        receipt=_receipt(
            amount="799.00", charged_at=datetime.datetime(2026, 6, 1, tzinfo=datetime.UTC)
        ),
    )
    second = await service.record_receipt(
        user_id=user_id,
        email_account_id=email_account_id,
        message_id="msg-3b",
        receipt=_receipt(
            amount="799.00", charged_at=datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
        ),
    )

    assert first is not None
    assert second is not None
    assert first.subscription_id == second.subscription_id


async def test_record_receipt_without_catalog_match_keys_on_sender_name(
    session: AsyncSession,
) -> None:
    user_id, email_account_id = await _make_email_account(session, 970004)
    service = await _make_receipt_service(session)

    receipt = _receipt(
        amount="4.99",
        currency="EUR",
        charged_at=datetime.datetime(2026, 5, 10, tzinfo=datetime.UTC),
        sender_name="Acme Cloud Storage",
        service_slug=None,
    )
    transaction = await service.record_receipt(
        user_id=user_id, email_account_id=email_account_id, message_id="msg-4", receipt=receipt
    )

    assert transaction is not None
    subscription = await SubscriptionRepository(session).get_by_id(transaction.subscription_id)
    assert subscription is not None
    assert subscription.service_id is None
    assert subscription.custom_name == "Acme Cloud Storage"


async def test_period_self_corrects_after_second_transaction(session: AsyncSession) -> None:
    user_id, email_account_id = await _make_email_account(session, 970005)
    service = await _make_receipt_service(session)

    first = await service.record_receipt(
        user_id=user_id,
        email_account_id=email_account_id,
        message_id="msg-5a",
        receipt=_receipt(
            amount="299.00", charged_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC)
        ),
    )
    assert first is not None
    subscription = await SubscriptionRepository(session).get_by_id(first.subscription_id)
    assert subscription is not None
    assert subscription.period == SubscriptionPeriod.MONTHLY  # default guess, no evidence yet

    # ~90 days later - the real cadence turns out to be quarterly.
    await service.record_receipt(
        user_id=user_id,
        email_account_id=email_account_id,
        message_id="msg-5b",
        receipt=_receipt(
            amount="299.00", charged_at=datetime.datetime(2026, 4, 1, tzinfo=datetime.UTC)
        ),
    )

    # record_receipt() already flushes; confirm the correction actually hit the
    # DB (not just the in-memory object) before asserting.
    await session.flush()
    await session.refresh(subscription)
    assert subscription.period == SubscriptionPeriod.QUARTERLY
    assert subscription.next_charge_at == datetime.datetime(2026, 7, 1, tzinfo=datetime.UTC)
