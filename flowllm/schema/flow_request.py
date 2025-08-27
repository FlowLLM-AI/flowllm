from typing import List

from pydantic import Field, BaseModel

from flowllm.schema.message import Message


class FlowRequest(BaseModel, extra="allow"):
    query: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    workspace_id: str = Field(default="")
    metadata: dict = Field(default_factory=dict)
