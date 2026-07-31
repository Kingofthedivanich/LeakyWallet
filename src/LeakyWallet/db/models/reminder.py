import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from LeakyWallet.db.base import Base, CreatedAtMixin
from LeakyWallet.db.models.user import ReminderPolicy

if TYPE_CHECKING:
    from LeakyWallet.db.models.subscription import Subscription
    from LeakyWallet.db.models.user import User


class Reminder(CreatedAtMixin, Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
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

    user: Mapped["User"] = relationship(back_populates="reminders")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="reminders")
