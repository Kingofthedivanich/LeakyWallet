import datetime
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from LeakyWallet.db.models.subscription import SubscriptionPeriod
from LeakyWallet.mail.base import RawMessage
from LeakyWallet.parsing.pipeline import parse_message

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "emails"


def _load_fixtures() -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        (path.stem, json.loads(path.read_text(encoding="utf-8")))
        for path in _FIXTURES_DIR.glob("*.json")
    )


FIXTURES = _load_fixtures()


def test_fixtures_directory_is_not_empty() -> None:
    assert len(FIXTURES) >= 5


@pytest.mark.parametrize("name,fixture", FIXTURES, ids=[name for name, _ in FIXTURES])
async def test_fixture_parses_as_expected(name: str, fixture: dict[str, Any]) -> None:
    message = RawMessage(
        message_id=fixture["message_id"],
        sender=fixture["sender"],
        subject=fixture["subject"],
        snippet=fixture["snippet"],
        received_at=datetime.datetime.fromisoformat(fixture["received_at"]),
    )

    result = await parse_message(message, user_id=1)
    expected = fixture["expected"]

    if expected is None:
        assert result is None, f"{name}: expected unparseable, got {result}"
        return

    assert result is not None, f"{name}: expected a parsed receipt, got None"
    assert result.amount == Decimal(expected["amount"])
    assert result.currency == expected["currency"]
    assert result.service_slug == expected["service_slug"]

    if expected.get("period") is not None:
        assert result.period == SubscriptionPeriod(expected["period"])
    else:
        assert result.period is None

    if "sender_name" in expected:
        assert result.sender_name == expected["sender_name"]


async def test_reparsing_same_fixture_is_deterministic() -> None:
    name, fixture = FIXTURES[0]
    message = RawMessage(
        message_id=fixture["message_id"],
        sender=fixture["sender"],
        subject=fixture["subject"],
        snippet=fixture["snippet"],
        received_at=datetime.datetime.fromisoformat(fixture["received_at"]),
    )

    first = await parse_message(message, user_id=1)
    second = await parse_message(message, user_id=1)
    assert first == second
