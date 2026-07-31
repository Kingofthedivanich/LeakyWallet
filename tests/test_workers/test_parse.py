import datetime
from typing import Any

from LeakyWallet.workers.parse import parse_candidate


async def test_parse_candidate_does_not_raise() -> None:
    ctx: dict[str, Any] = {}
    await parse_candidate(
        ctx,
        1,
        "msg-1",
        "billing@netflix.com",
        "Receipt",
        "snippet",
        datetime.datetime.now(datetime.UTC).isoformat(),
    )
