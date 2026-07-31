from functools import lru_cache

from redis.asyncio import Redis

from LeakyWallet.config import get_settings


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(str(settings.redis_url))  # type: ignore[no-any-return]
