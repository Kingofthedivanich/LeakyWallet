import datetime
import json

from LeakyWallet.db.models.email_account import EmailAccount, EmailAccountStatus, EmailProvider
from LeakyWallet.mail.crypto import decrypt_token, encrypt_token
from LeakyWallet.mail.oauth import TokenResponse, refresh_access_token
from LeakyWallet.repositories.email_accounts import EmailAccountRepository

EXPIRY_SAFETY_MARGIN = datetime.timedelta(minutes=2)


def _serialize(tokens: TokenResponse, *, expires_at: datetime.datetime) -> str:
    return json.dumps(
        {
            "access_token": tokens.access_token,
            "refresh_token": tokens.refresh_token,
            "expires_at": expires_at.isoformat(),
        }
    )


def _deserialize(payload: str) -> dict[str, str]:
    data: dict[str, str] = json.loads(payload)
    return data


class EmailAccountService:
    def __init__(self, repository: EmailAccountRepository) -> None:
        self._repository = repository

    async def connect(self, *, user_id: int, email: str, tokens: TokenResponse) -> EmailAccount:
        if tokens.refresh_token is None:
            raise ValueError("Google did not return a refresh token")

        expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            seconds=tokens.expires_in
        )
        encrypted = encrypt_token(_serialize(tokens, expires_at=expires_at))

        existing = await self._repository.get_by_user_and_provider(user_id, EmailProvider.GMAIL)
        if existing is not None:
            existing.email = email
            existing.encrypted_token = encrypted
            existing.status = EmailAccountStatus.ACTIVE
            return existing

        return await self._repository.create(
            user_id=user_id, provider=EmailProvider.GMAIL, email=email, encrypted_token=encrypted
        )

    async def disconnect(self, email_account: EmailAccount) -> None:
        await self._repository.delete(email_account)

    async def get_valid_access_token(self, email_account: EmailAccount) -> str:
        data = _deserialize(decrypt_token(email_account.encrypted_token))
        expires_at = datetime.datetime.fromisoformat(data["expires_at"])

        if datetime.datetime.now(datetime.UTC) + EXPIRY_SAFETY_MARGIN < expires_at:
            return data["access_token"]

        refreshed = await refresh_access_token(data["refresh_token"])
        new_expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            seconds=refreshed.expires_in
        )
        email_account.encrypted_token = encrypt_token(
            _serialize(refreshed, expires_at=new_expires_at)
        )
        return refreshed.access_token
