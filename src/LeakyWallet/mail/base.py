import datetime
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawMessage:
    message_id: str
    sender: str
    subject: str
    snippet: str
    received_at: datetime.datetime


class MailClient(Protocol):
    async def fetch_since(self, cursor: str | None) -> tuple[list[RawMessage], str]: ...
