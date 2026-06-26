"""Service response schema."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Response(BaseModel):
    """Standard response envelope with extra fields for endpoint output."""

    model_config = ConfigDict(extra="allow")

    answer: str | Any = Field(default="", description="Response content or result data")
    success: bool = Field(default=True, description="Whether the operation succeeded")
    metadata: dict = Field(default_factory=dict, description="Additional context and diagnostics")
