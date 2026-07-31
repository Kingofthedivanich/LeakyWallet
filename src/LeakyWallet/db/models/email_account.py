import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LeakyWallet.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from LeakyWallet.db.models.transaction import Transaction
    from LeakyWallet.db.models.user import User


class EmailProvider(enum.StrEnum):
    GMAIL = "gmail"
    IMAP = "imap"


class EmailAccountStatus(enum.StrEnum):
    ACTIVE = "active"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class EmailAccount(TimestampMixin, Base):
    __tablename__ = "email_accounts"
    __table_args__ = (UniqueConstraint("user_id", "email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[EmailProvider] = mapped_column(
        SqlEnum(
            EmailProvider,
            name="email_provider",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    encrypted_token: Mapped[str] = mapped_column(Text, nullable=False)
    cursor: Mapped[str | None] = mapped_column(String(255))
    last_synced_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[EmailAccountStatus] = mapped_column(
        SqlEnum(
            EmailAccountStatus,
            name="email_account_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=EmailAccountStatus.ACTIVE.value,
    )

    user: Mapped["User"] = relationship(back_populates="email_accounts")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="email_account")
