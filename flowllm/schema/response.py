from typing import List

from pydantic import BaseModel, Field

from flowllm.schema.message import Message


class BaseResponse(BaseModel):
    success: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)


class AgentResponse(BaseResponse):
    answer: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)


class FinResponse(BaseResponse):
    answer: str = Field(default="")
    path: str = Field(default="")
