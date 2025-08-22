from abc import ABC, abstractmethod

from flowllm.flow.base_flow import BaseFlow
from flowllm.schema.tool_call import ToolCall


class BaseToolFlow(BaseFlow, ABC):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.tool_call: ToolCall = self.build_tool_call()

    @abstractmethod
    def build_tool_call(self) -> ToolCall:
        ...
