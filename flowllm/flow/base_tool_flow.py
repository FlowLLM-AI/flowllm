from abc import ABC

from flowllm.flow.base_flow import BaseFlow
from flowllm.schema.tool_call import ToolCall


class BaseToolFlow(BaseFlow, ABC):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tool_call: ToolCall | None = None

    def build_tool_call(self) -> ToolCall:
        ...

    @property
    def tool_call(self) -> ToolCall:
        if self._tool_call is None:
            self._tool_call = self.build_tool_call()
        return self._tool_call

    async def rebuild_tool_call(self):
        ...
