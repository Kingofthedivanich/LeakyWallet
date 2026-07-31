from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from LeakyWallet.db.base import Base


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_patterns: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    cancel_url: Mapped[str | None] = mapped_column(String(512))
