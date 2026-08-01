from collections.abc import Sequence

from LeakyWallet.db.models.subscription import Subscription, SubscriptionPeriod
from LeakyWallet.db.models.transaction import Transaction
from LeakyWallet.parsing import catalog
from LeakyWallet.parsing.schemas import ParsedReceipt
from LeakyWallet.repositories.services import ServiceRepository
from LeakyWallet.repositories.subscriptions import SubscriptionRepository
from LeakyWallet.repositories.transactions import TransactionRepository
from LeakyWallet.utils.dates import add_period, has_same_day_repeat, infer_period_from_intervals
from LeakyWallet.utils.money import amounts_are_consistent

# Most real-world subscriptions bill monthly; used only when the receipt text
# doesn't state a period explicitly. Self-corrects via _refine_period once a
# second transaction lands and the actual interval can be measured.
_DEFAULT_PERIOD = SubscriptionPeriod.MONTHLY

# Below this many transactions, amount/date variance is too noisy to tell a
# recurring subscription from a couple of one-off purchases that happened to
# match the same sender/service.
_MIN_TRANSACTIONS_FOR_RECURRING_CHECK = 3


class ReceiptService:
    def __init__(
        self,
        subscriptions: SubscriptionRepository,
        transactions: TransactionRepository,
        services: ServiceRepository,
    ) -> None:
        self._subscriptions = subscriptions
        self._transactions = transactions
        self._services = services

    async def record_receipt(
        self, *, user_id: int, email_account_id: int, message_id: str, receipt: ParsedReceipt
    ) -> Transaction | None:
        if await self._transactions.exists(
            email_account_id=email_account_id, message_id=message_id
        ):
            return None

        subscription = await self._find_or_create_subscription(user_id=user_id, receipt=receipt)

        transaction = await self._transactions.create(
            subscription_id=subscription.id,
            charged_at=receipt.charged_at,
            amount=receipt.amount,
            currency=receipt.currency,
            email_account_id=email_account_id,
            message_id=message_id,
        )

        all_transactions = await self._transactions.list_by_subscription(subscription.id)
        self._refine_period(subscription, all_transactions)
        self._refine_recurring_flag(subscription, all_transactions)
        return transaction

    async def _find_or_create_subscription(
        self, *, user_id: int, receipt: ParsedReceipt
    ) -> Subscription:
        service_id: int | None = None

        if receipt.service_slug is not None:
            entry = catalog.get_entry(receipt.service_slug)
            service = (
                await self._services.get_or_create(
                    slug=entry.slug,
                    name=entry.name,
                    domain_patterns=list(entry.domain_patterns),
                    cancel_url=entry.cancel_url,
                    category=entry.category,
                )
                if entry is not None
                else None
            )
            service_id = service.id if service is not None else None

        period = receipt.period or _DEFAULT_PERIOD
        return await self._subscriptions.get_or_create_email(
            user_id=user_id,
            service_id=service_id,
            custom_name=receipt.sender_name,
            amount=receipt.amount,
            currency=receipt.currency,
            period=period,
            next_charge_at=add_period(receipt.charged_at, period),
        )

    def _refine_period(
        self, subscription: Subscription, transactions: Sequence[Transaction]
    ) -> None:
        if len(transactions) < 2:
            return

        inferred = infer_period_from_intervals([t.charged_at for t in transactions])
        if inferred is None or inferred == subscription.period:
            return

        subscription.period = inferred
        latest_charge = max(t.charged_at for t in transactions)
        subscription.next_charge_at = add_period(latest_charge, inferred)

    def _refine_recurring_flag(
        self, subscription: Subscription, transactions: Sequence[Transaction]
    ) -> None:
        if len(transactions) < _MIN_TRANSACTIONS_FOR_RECURRING_CHECK:
            return
        if not subscription.is_recurring:
            return  # already flagged - no way back without a manual edit

        charged_dates = [t.charged_at for t in transactions]
        amounts = [t.amount for t in transactions]
        if has_same_day_repeat(charged_dates) or not amounts_are_consistent(amounts):
            subscription.is_recurring = False
