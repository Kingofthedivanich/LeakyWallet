import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from LeakyWallet.db.models.email_account import EmailProvider
from LeakyWallet.mail.oauth import TokenResponse
from LeakyWallet.repositories.email_accounts import EmailAccountRepository
from LeakyWallet.repositories.users import UserRepository
from LeakyWallet.services.email_accounts import EmailAccountService


async def test_connect_creates_email_account(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900101, timezone="UTC", base_currency="USD")

    service = EmailAccountService(EmailAccountRepository(session))
    tokens = TokenResponse(access_token="access", refresh_token="refresh", expires_in=3600)
    account = await service.connect(user_id=user.id, email="user@gmail.com", tokens=tokens)

    assert account.email == "user@gmail.com"
    assert account.provider == EmailProvider.GMAIL
    assert account.encrypted_token != "access"


async def test_connect_without_refresh_token_raises(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900102, timezone="UTC", base_currency="USD")

    service = EmailAccountService(EmailAccountRepository(session))
    tokens = TokenResponse(access_token="access", refresh_token=None, expires_in=3600)

    with pytest.raises(ValueError, match="refresh token"):
        await service.connect(user_id=user.id, email="user@gmail.com", tokens=tokens)


async def test_connect_twice_updates_existing_account(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900103, timezone="UTC", base_currency="USD")

    service = EmailAccountService(EmailAccountRepository(session))
    first = await service.connect(
        user_id=user.id,
        email="old@gmail.com",
        tokens=TokenResponse(access_token="a1", refresh_token="r1", expires_in=3600),
    )
    second = await service.connect(
        user_id=user.id,
        email="new@gmail.com",
        tokens=TokenResponse(access_token="a2", refresh_token="r2", expires_in=3600),
    )

    assert first.id == second.id
    assert second.email == "new@gmail.com"


async def test_get_valid_access_token_returns_cached_when_not_expired(
    session: AsyncSession,
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900104, timezone="UTC", base_currency="USD")

    service = EmailAccountService(EmailAccountRepository(session))
    account = await service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="fresh-access", refresh_token="r1", expires_in=3600),
    )

    assert await service.get_valid_access_token(account) == "fresh-access"


async def test_get_valid_access_token_refreshes_when_expired(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900105, timezone="UTC", base_currency="USD")

    service = EmailAccountService(EmailAccountRepository(session))
    account = await service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="old-access", refresh_token="r1", expires_in=-10),
    )

    async def fake_refresh(refresh_token: str) -> TokenResponse:
        assert refresh_token == "r1"
        return TokenResponse(access_token="refreshed-access", refresh_token="r1", expires_in=3600)

    monkeypatch.setattr("LeakyWallet.services.email_accounts.refresh_access_token", fake_refresh)

    assert await service.get_valid_access_token(account) == "refreshed-access"


async def test_disconnect_deletes_email_account(session: AsyncSession) -> None:
    users = UserRepository(session)
    user = await users.create(tg_id=900106, timezone="UTC", base_currency="USD")

    repository = EmailAccountRepository(session)
    service = EmailAccountService(repository)
    account = await service.connect(
        user_id=user.id,
        email="user@gmail.com",
        tokens=TokenResponse(access_token="a", refresh_token="r", expires_in=3600),
    )

    await service.disconnect(account)
    await session.flush()

    assert await repository.get_by_user_and_provider(user.id, EmailProvider.GMAIL) is None
