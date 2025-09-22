import asyncio

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class ThinkToolOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "think_tool",
            "description": """
Tool for strategic reflection on research progress and decision-making.

Use this tool after each search to analyze results and plan next steps systematically.
This creates a deliberate pause in the research workflow for quality decision-making.

When to use:
- After receiving search results: What key information did I find?
- Before deciding next steps: Do I have enough to answer comprehensively?
- When assessing research gaps: What specific information am I still missing?
- Before concluding research: Can I provide a complete answer now?

Reflection should address:
1. Analysis of current findings - What concrete information have I gathered?
2. Gap assessment - What crucial information is still missing?
3. Quality evaluation - Do I have sufficient evidence/examples for a good answer?
4. Strategic decision - Should I continue searching or provide my answer?
            """.strip(),
            "input_schema": {
                "reflection": {
                    "type": "str",
                    "description": "Your detailed reflection on research progress, findings, gaps, and next steps.",
                    "required": True,
                }
            }
        })

    async def async_execute(self):
        reflection: str = self.input_dict["reflection"]
        self.set_result(f"Reflection recorded: {reflection}")


async def main():
    op = ThinkToolOp()
    context = FlowContext(reflection="haha")
    await op.async_call(context)
    print(f"Result: {op.output}")


if __name__ == "__main__":
    asyncio.run(main())
