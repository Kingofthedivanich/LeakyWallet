from typing import Any

from LeakyWallet.logging import get_logger

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
    # Placeholder consumer for the parsing queue - real parsing (catalog match,
    # regex extraction, dedup-by-message_id, Subscription upsert) lands in the
    # next stage. For now this just proves the scan -> queue -> parse pipeline
    # is wired end to end.
    logger.info(
        "received parsing candidate",
        email_account_id=email_account_id,
        message_id=message_id,
        sender=sender,
        subject=subject,
    )
