import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LeakyWallet.db.base import Base, CreatedAtMixin
from LeakyWallet.db.models.user import ReminderPolicy

if TYPE_CHECKING:
    from LeakyWallet.db.models.subscription import Subscription


class Reminder(CreatedAtMixin, Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[ReminderPolicy] = mapped_column(
        SqlEnum(
            ReminderPolicy,
            name="reminder_kind",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    fire_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    sent_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    subscription: Mapped["Subscription"] = relationship(back_populates="reminders")
