import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LeakyWallet.db.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from LeakyWallet.db.models.email_account import EmailAccount
    from LeakyWallet.db.models.subscription import Subscription


class Transaction(CreatedAtMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("email_account_id", "message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("email_accounts.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[str | None] = mapped_column(String(255))
    charged_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    subscription: Mapped["Subscription"] = relationship(back_populates="transactions")
    email_account: Mapped["EmailAccount | None"] = relationship(back_populates="transactions")
