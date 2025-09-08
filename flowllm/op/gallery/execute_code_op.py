import asyncio
import sys
from io import StringIO

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.op.base_tool_op import BaseToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op()
class ExecuteCodeOp(BaseToolOp):

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
            code_key: str = self.op_params.get("code_key", "code")
            code_str: str = self.context[code_key]
            exec(code_str)
            code_result = redirected_output.getvalue()

        except Exception as e:
            logger.info(f"{self.name} encounter exception! error={e.args}")
            code_result = str(e)

        sys.stdout = old_stdout
        self.output_dict[self.output_keys] = code_result

    async def async_execute(self):
        old_stdout = sys.stdout
        redirected_output = sys.stdout = StringIO()

        try:
            code_key: str = self.op_params.get("code_key", "code")
            code_str: str = self.context[code_key]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(C.thread_pool, lambda: exec(code_str))  # noqa

            code_result = redirected_output.getvalue()

        except Exception as e:
            logger.info(f"{self.name} encounter exception! error={e.args}")
            code_result = str(e)

        sys.stdout = old_stdout
        self.set_result(code_result)


async def async_main():
    C.set_service_config().init_by_service_config()
    op = ExecuteCodeOp()

    context = FlowContext(code="print('Hello World')")
    await op.async_call(context=context)
    print(op.output)

    context.code = "print('Hello World!'"
    await op.async_call(context=context)
    print(op.output)


if __name__ == "__main__":
    asyncio.run(async_main())
