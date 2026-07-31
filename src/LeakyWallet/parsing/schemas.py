import datetime
from decimal import Decimal

from pydantic import BaseModel

from LeakyWallet.db.models.subscription import SubscriptionPeriod


class ParsedReceipt(BaseModel):
    amount: Decimal
    currency: str
    charged_at: datetime.datetime
    period: SubscriptionPeriod | None = None
    sender_name: str
    service_slug: str | None = None
    service_name: str | None = None
