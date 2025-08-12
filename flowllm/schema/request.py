from typing import List

from pydantic import BaseModel, Field

from flowllm.schema.message import Message


class BaseRequest(BaseModel):
    flow_name: str = Field(default="default")
    workspace_id: str = Field(default="default")
    config: dict = Field(default_factory=dict)


class AgentRequest(BaseRequest):
    query: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)


class FinRequest(BaseRequest):
    query: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    code_infos: dict = Field(default_factory=dict)
