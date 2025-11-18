import asyncio

from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class TaskCompleteOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "task_complete",
            "description": "Call this tool to indicate that the task is complete.",
        })

    async def async_execute(self):
        self.set_result(f"The task is complete.")

