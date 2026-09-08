from datetime import datetime

from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    status: str = Field(default="ok", description="Service status")
    service: str = Field(description="Service name")
    environment: str = Field(description="Environment mode")
    timestamp: datetime = Field(description="Current server time")


class DbHealthResponse(BaseModel):
    status: str = Field(description="'connected' or 'disconnected'")
    database: str = Field(description="Database engine type")
    error: str | None = Field(default=None, description="Error message if disconnected")
    timestamp: datetime = Field(description="Current server time")
