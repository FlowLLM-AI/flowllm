import asyncio

from loguru import logger

from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class MockExceptionOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "description": "mock exception tool",
            "input_schema": {
                "query": {
                    "type": "string",
                    "description": "query",
                    "required": True
                }
            }})

    async def async_execute(self):
        query = self.input_dict.get("query")
        await asyncio.sleep(1)
        logger.info(f"start mock exception with {query}")

        if query == "run_time":
            raise RuntimeError("run_time error")

        elif query == "value":
            raise ValueError("value error")

        elif query == "not_im":
            raise NotImplementedError("not_im error")

        self.set_result("normal")
