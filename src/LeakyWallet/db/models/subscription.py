import datetime
import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LeakyWallet.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from LeakyWallet.db.models.reminder import Reminder
    from LeakyWallet.db.models.service import Service
    from LeakyWallet.db.models.transaction import Transaction
    from LeakyWallet.db.models.user import User


class SubscriptionPeriod(enum.StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class SubscriptionSource(enum.StrEnum):
    MANUAL = "manual"
    EMAIL = "email"


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"
    # Two parse_candidate jobs for the same catalog-matched service (or the
    # same unmatched sender) can otherwise both find "no existing subscription
    # yet" and both insert - these partial indexes make the DB reject the
    # second insert instead of silently duplicating it. Scoped to source=email
    # only: manual subscriptions may legitimately share a name/service.
    __table_args__ = (
        Index(
            "uq_subscriptions_user_service_email",
            "user_id",
            "service_id",
            unique=True,
            postgresql_where=text("source = 'email' AND service_id IS NOT NULL"),
        ),
        Index(
            "uq_subscriptions_user_custom_name_email",
            "user_id",
            "custom_name",
            unique=True,
            postgresql_where=text("source = 'email' AND service_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"), index=True
    )
    custom_name: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period: Mapped[SubscriptionPeriod] = mapped_column(
        SqlEnum(
            SubscriptionPeriod,
            name="subscription_period",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    next_charge_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SqlEnum(
            SubscriptionStatus,
            name="subscription_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=SubscriptionStatus.ACTIVE.value,
    )
    source: Mapped[SubscriptionSource] = mapped_column(
        SqlEnum(
            SubscriptionSource,
            name="subscription_source",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    # Self-corrects once 3+ transactions land (services/receipts.py) - same-day
    # repeat charges or wildly varying amounts mean this is a string of one-off
    # purchases (e.g. Steam game buys) that happened to match the catalog, not
    # an actual recurring subscription.
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    service: Mapped["Service | None"] = relationship()
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )
