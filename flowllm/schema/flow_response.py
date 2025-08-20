from typing import List

from pydantic import Field, BaseModel

from flowllm.schema.message import Message


class FlowResponse(BaseModel):
    answer: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    success: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)
