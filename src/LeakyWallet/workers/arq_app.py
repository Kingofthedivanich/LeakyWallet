from typing import Any

from arq.connections import RedisSettings

from LeakyWallet.config import get_settings

settings = get_settings()


async def healthcheck(ctx: dict[str, Any]) -> str:
    return "ok"


class WorkerSettings:
    functions = [healthcheck]
    cron_jobs: list[object] = []
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
