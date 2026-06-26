"""Service request schema."""

from pydantic import BaseModel, ConfigDict, Field


class Request(BaseModel):
    """Incoming service request with extra fields for endpoint payloads."""

    model_config = ConfigDict(extra="allow")

    metadata: dict | None = Field(default=None, description="Request metadata for context")
