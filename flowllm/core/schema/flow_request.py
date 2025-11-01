"""Flow request schema for API requests."""

from typing import List

from pydantic import Field, BaseModel, ConfigDict

from .message import Message


class FlowRequest(BaseModel):
    """Represents a flow execution request with query, messages, and workspace context."""

    query: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    workspace_id: str = Field(default="")
    metadata: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")
