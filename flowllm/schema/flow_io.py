import uuid
from typing import List

from pydantic import BaseModel, Field

from flowllm.schema.message import Message


class FlowRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    workspace_id: str = Field(default="default", description="workspace id")
    service_config: dict = Field(default_factory=dict, description="{xxx.xxx:xxx}")
    flow_name: str = Field(default=...)
    # query: str = Field(default="")
    # messages: List[Message] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class FlowResponse(BaseModel):
    answer: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    output_path: str = Field(default="")
    success: bool = Field(default=True)
    metadata: dict = Field(default_factory=dict)
