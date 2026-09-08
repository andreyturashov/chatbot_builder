import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class BotStatus(enum.StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    READY = "ready"
    DEPLOYED = "deployed"


class Bot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "bots"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    status: Mapped[BotStatus] = mapped_column(
        Enum(BotStatus, native_enum=False, length=32),
        default=BotStatus.DRAFT,
        nullable=False,
        index=True,
    )

    owner: Mapped["User | None"] = relationship("User", back_populates="bots")
