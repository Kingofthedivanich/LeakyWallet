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


class LLMReceiptFields(BaseModel):
    # sender_name/service_slug сюда не входят - их всегда определяет catalog.py в pipeline.py
    is_charge: bool
    amount: Decimal | None = None
    currency: str | None = None
    period: SubscriptionPeriod | None = None
