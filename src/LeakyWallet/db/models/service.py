import enum

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from LeakyWallet.db.base import Base


class ServiceCategory(enum.StrEnum):
    STREAMING = "streaming"
    MUSIC = "music"
    CLOUD_STORAGE = "cloud_storage"
    PRODUCTIVITY = "productivity"
    GAMING = "gaming"
    AI = "ai"
    EDUCATION = "education"
    UTILITIES = "utilities"
    SHOPPING = "shopping"
    SOCIAL = "social"
    OTHER = "other"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_patterns: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    cancel_url: Mapped[str | None] = mapped_column(String(512))
    category: Mapped[ServiceCategory] = mapped_column(
        SqlEnum(
            ServiceCategory,
            name="service_category",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=ServiceCategory.OTHER.value,
    )
