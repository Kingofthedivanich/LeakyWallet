import datetime
import re
from decimal import Decimal

from LeakyWallet.mail.base import RawMessage
from LeakyWallet.parsing import catalog, llm, rules
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


async def parse_message(message: RawMessage, *, user_id: int) -> ParsedReceipt | None:
    text = f"{message.subject}\n{message.snippet}"

    amount_currency = rules.extract_amount_and_currency(text)
    if amount_currency is not None:
        amount, currency = amount_currency
        period = rules.extract_period(text)
    else:
        llm_fields = await llm.extract_with_llm(text, user_id=user_id)
        if llm_fields is None or not llm_fields.is_charge or llm_fields.amount is None:
            return None
        if llm_fields.currency is None or llm_fields.amount <= 0:
            return None
        amount = llm_fields.amount.quantize(Decimal("0.01"))
        currency = llm_fields.currency.upper()
        period = llm_fields.period or rules.extract_period(text)

    extracted_date = rules.extract_date(text)
    charged_at = (
        datetime.datetime.combine(extracted_date, datetime.time(12), tzinfo=datetime.UTC)
        if extracted_date is not None
        else message.received_at
    )

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
