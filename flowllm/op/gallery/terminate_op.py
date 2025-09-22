import asyncio

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class TerminateOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "terminate",
            "description": "If you can answer the question based on the context, be sure to use the **terminate** tool.",
            "input_schema": {
                "status": {
                    "type": "str",
                    "description": "If the user's question can be answered, return success, otherwise return failure.",
                    "required": True,
                    "enum": ["success", "failure"],
                }
            }
        })

    async def async_execute(self):
        status: str = self.input_dict["status"]
        assert status in ["success", "failure"], f"Invalid status: {status}"
        self.set_result(f"The interaction has been completed with status: {status}")


async def main():
    op = TerminateOp()
    context = FlowContext(status="success")
    await op.async_call(context)
    print(f"Result: {op.output}")


if __name__ == "__main__":
    asyncio.run(main())
