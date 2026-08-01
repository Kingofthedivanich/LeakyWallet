import sentry_sdk

from LeakyWallet.config import get_settings


def init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.0,
    )
