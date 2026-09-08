import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.bot import BotStatus


class BotBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the bot")
    description: str | None = Field(default=None, description="Business context or purpose")
    system_prompt: str | None = Field(
        default=None, description="Base persona/instruction for the agent"
    )
    settings: dict[str, Any] = Field(
        default_factory=dict, description="Custom parameters (model, temperature, etc.)"
    )


class BotCreate(BotBase):
    pass


class BotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    system_prompt: str | None = None
    settings: dict[str, Any] | None = None
    status: BotStatus | None = None


class BotResponse(BotBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    status: BotStatus
    created_at: datetime
    updated_at: datetime


class BotListResponse(BaseModel):
    items: list[BotResponse]
    total: int = Field(ge=0)
    skip: int = Field(ge=0)
    limit: int = Field(gt=0)
