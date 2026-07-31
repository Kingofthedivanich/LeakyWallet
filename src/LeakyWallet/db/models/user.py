import enum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LeakyWallet.db.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from LeakyWallet.db.models.email_account import EmailAccount
    from LeakyWallet.db.models.subscription import Subscription


class ReminderPolicy(enum.StrEnum):
    OFF = "off"
    DAYS_BEFORE = "days_before"
    WEEKLY_DIGEST = "weekly_digest"
    MONTHLY_REPORT = "monthly_report"


class User(CreatedAtMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="USD")
    reminder_policy: Mapped[ReminderPolicy] = mapped_column(
        SqlEnum(
            ReminderPolicy,
            name="reminder_policy",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=ReminderPolicy.OFF.value,
    )

    email_accounts: Mapped[list["EmailAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
