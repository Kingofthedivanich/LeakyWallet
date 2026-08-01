import csv
import io
from collections.abc import Sequence

from LeakyWallet.db.models.transaction import Transaction

CSV_HEADER = ("subscription", "amount", "currency", "charged_at")


def transactions_to_csv(transactions: Sequence[Transaction]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for transaction in transactions:
        name = transaction.subscription.custom_name or "Подписка"
        writer.writerow(
            [
                name,
                str(transaction.amount),
                transaction.currency,
                transaction.charged_at.isoformat(),
            ]
        )

    return buffer.getvalue()
