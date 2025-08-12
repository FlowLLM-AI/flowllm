from typing import List

from pydantic import BaseModel, Field

from flowllm.schema.message import Message


class BaseRequest(BaseModel):
    workspace_id: str = Field(default="default")
    config: dict = Field(default_factory=dict)
    flow_name: str = Field(default="default")


class AgentRequest(BaseRequest):
    query: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)


class FinSupplyRequest(BaseRequest):
    query: str = Field(default="")
    codes: List[str] = Field(default_factory=list)
