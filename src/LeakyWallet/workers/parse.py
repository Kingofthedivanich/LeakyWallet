import datetime
from typing import Any

from LeakyWallet.logging import get_logger
from LeakyWallet.mail.base import RawMessage
from LeakyWallet.parsing.pipeline import parse_message
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.services.receipts import ReceiptService

logger = get_logger(__name__)


async def parse_candidate(
    ctx: dict[str, Any],
    email_account_id: int,
    message_id: str,
    sender: str,
    subject: str,
    snippet: str,
    received_at: str,
) -> None:
    session_factory = ctx["session_factory"]

    async with session_factory() as session:
        email_repo = EmailAccountRepository(session)
        email_account = await email_repo.get_by_id(email_account_id)
        if email_account is None:
            return

        transactions_repo = TransactionRepository(session)
        if await transactions_repo.exists(email_account_id=email_account_id, message_id=message_id):
            logger.debug("candidate already processed", message_id=message_id)
            return

        message = RawMessage(
            message_id=message_id,
            sender=sender,
            subject=subject,
            snippet=snippet,
            received_at=datetime.datetime.fromisoformat(received_at),
        )
        receipt = await parse_message(message, user_id=email_account.user_id)
        if receipt is None:
            logger.info("could not parse candidate", message_id=message_id)
            return

        receipt_service = ReceiptService(
            SubscriptionRepository(session), transactions_repo, ServiceRepository(session)
        )
        transaction = await receipt_service.record_receipt(
            user_id=email_account.user_id,
            email_account_id=email_account_id,
            message_id=message_id,
            receipt=receipt,
        )
        await session.commit()

        if transaction is not None:
            logger.info(
                "recorded transaction from email",
                message_id=message_id,
                subscription_id=transaction.subscription_id,
                amount=str(receipt.amount),
                currency=receipt.currency,
            )
