"""Flow response schema for API responses."""

from typing import List

from pydantic import Field, BaseModel

from .message import Message


class FlowResponse(BaseModel):
    """Represents a complete flow execution response with answer and messages."""

    answer: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    success: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)
