import datetime
import re

from LeakyWallet.mail.base import RawMessage
from LeakyWallet.parsing import catalog, rules
from LeakyWallet.parsing.schemas import ParsedReceipt

_DISPLAY_NAME_PATTERN = re.compile(r'^\s*"?([^"<]+?)"?\s*<')
_DOMAIN_PATTERN = re.compile(r"@([\w.-]+)")


def _extract_sender_name(sender: str) -> str:
    match = _DISPLAY_NAME_PATTERN.match(sender)
    if match:
        name = match.group(1).strip()
        if name:
            return name

    domain_match = _DOMAIN_PATTERN.search(sender)
    if domain_match:
        return domain_match.group(1)

    return sender.strip() or "Подписка"


def parse_message(message: RawMessage) -> ParsedReceipt | None:
    text = f"{message.subject}\n{message.snippet}"

    amount_currency = rules.extract_amount_and_currency(text)
    if amount_currency is None:
        return None
    amount, currency = amount_currency

    extracted_date = rules.extract_date(text)
    charged_at = (
        datetime.datetime.combine(extracted_date, datetime.time(12), tzinfo=datetime.UTC)
        if extracted_date is not None
        else message.received_at
    )

    period = rules.extract_period(text)
    matched = catalog.match_sender(message.sender)

    return ParsedReceipt(
        amount=amount,
        currency=currency,
        charged_at=charged_at,
        period=period,
        sender_name=matched.name if matched else _extract_sender_name(message.sender),
        service_slug=matched.slug if matched else None,
        service_name=matched.name if matched else None,
    )
