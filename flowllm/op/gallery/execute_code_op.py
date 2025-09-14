import asyncio
import sys
from io import StringIO

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class ExecuteCodeOp(BaseAsyncToolOp):

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "python_execute",
            "description": "Execute python code can be used in scenarios such as analysis or calculation, and the final result can be printed using the `print` function.",
            "input_schema": {
                "code": {
                    "type": "string",
                    "description": "code to be executed. Please do not execute any matplotlib code here.",
                    "required": True
                }
            },
            "output_schema": {
                "code_result": {
                    "type": "string",
                    "description": "code execution result",
                }
            }
        })

    def execute(self):
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()

        try:
            code: str = self.input_dict["code"]
            exec(code)
            code_result = redirected_output.getvalue()

        except Exception as e:
            logger.info(f"{self.name} encounter exception! error={e.args}")
            code_result = str(e)

        sys.stdout = old_stdout
        self.set_result(code_result)

    async def async_execute(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(C.thread_pool, lambda: self.execute())



async def async_main():
    op = ExecuteCodeOp()

    context = FlowContext(code="print('Hello World')")
    await op.async_call(context=context)
    print(op.output)

    context.code = "print('Hello World!'"
    await op.async_call(context=context)
    print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
