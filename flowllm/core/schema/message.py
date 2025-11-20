"""Message and trajectory schema definitions for conversation management."""

import datetime
from typing import List

from pydantic import BaseModel, Field

from .tool_call import ToolCall
from ..enumeration import Role


class Message(BaseModel):
    """Represents a message in a conversation with role, content, and optional tool calls."""

    role: Role = Field(default=Role.USER)
    content: str | bytes = Field(default="")
    reasoning_content: str = Field(default="")
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_call_id: str = Field(default="")
    time_created: str = Field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    metadata: dict = Field(default_factory=dict)

    def simple_dump(self, add_reasoning: bool = False) -> dict:
        """Convert Message to a simple dictionary format for API serialization."""
        result: dict = {"role": self.role.value, "content": self.content}

        if add_reasoning:
            result["reasoning_content"] = self.reasoning_content

        if self.tool_calls:
            result["tool_calls"] = [x.simple_output_dump() for x in self.tool_calls]
        return result

    @property
    def string_buffer(self) -> str:
        """Get a string representation of the message with role and content."""
        return f"{self.role.value}: {self.content}"


class Trajectory(BaseModel):
    """Represents a conversation trajectory with messages and optional scoring."""

    task_id: str = Field(default="")
    messages: List[Message] = Field(default_factory=list)
    score: float = Field(default=0.0)
    metadata: dict = Field(default_factory=dict)
