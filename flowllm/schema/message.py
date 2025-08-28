import datetime
from typing import List

from pydantic import BaseModel, Field

from flowllm.enumeration.role import Role
from flowllm.schema.tool_call import ToolCall


class Message(BaseModel):
    role: Role = Field(default=Role.USER)
    content: str | bytes = Field(default="")
    reasoning_content: str = Field(default="")
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_call_id: str = Field(default="")
    time_created: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    metadata: dict = Field(default_factory=dict)

    def simple_dump(self, add_reason_content: bool = True) -> dict:
        result: dict
        if self.content:
            result = {"role": self.role.value, "content": self.content}
        elif add_reason_content and self.reasoning_content:
            result = {"role": self.role.value, "content": self.reasoning_content}
        else:
            result = {"role": self.role.value, "content": ""}

        if self.tool_calls:
            result["tool_calls"] = [x.simple_output_dump() for x in self.tool_calls]
        return result


class Trajectory(BaseModel):
    task_id: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    score: float = Field(default=0.0)
    metadata: dict = Field(default_factory=dict)
