import asyncio

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class ResearchCompleteOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "research_complete",
            "description": "Call this tool to indicate that the research is complete.",
        })

    async def async_execute(self):
        self.set_result(f"The research is complete.")


async def main():
    op = ResearchCompleteOp()
    context = FlowContext()
    await op.async_call(context)
    print(f"Result: {op.output}")


if __name__ == "__main__":
    asyncio.run(main())
