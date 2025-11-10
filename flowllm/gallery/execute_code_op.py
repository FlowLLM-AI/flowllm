"""Execute code operation for running Python code dynamically."""

import asyncio
import sys
from io import StringIO

from loguru import logger

from ..core.context import C
from ..core.op.base_async_tool_op import BaseAsyncToolOp
from ..core.schema import ToolCall


@C.register_op()
class ExecuteCodeOp(BaseAsyncToolOp):
    """Operation for executing Python code dynamically.

    This operation allows for dynamic execution of Python code in scenarios such as
    analysis or calculation. The code output is captured from stdout and returned
    as the result. If execution fails, the exception message is returned.
    """

    def build_tool_call(self) -> ToolCall:
        """Build the tool call definition for code execution.

        Returns:
            ToolCall object defining the code execution tool with input schema.
        """
        return ToolCall(
            **{
                "description": "Execute python code can be used in scenarios such as analysis or calculation, "
                "and the final result can be printed using the `print` function.",
                "input_schema": {
                    "code": {
                        "type": "string",
                        "description": "code to be executed",
                        "required": True,
                    },
                },
            },
        )

    def execute(self):
        """Execute the Python code from input_dict.

        Captures stdout output and handles exceptions. The result is set using
        set_result() method.
        """
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
        self.set_output(code_result)

    async def async_execute(self):
        """Execute code asynchronously in a thread pool.

        Runs the synchronous execute() method in a thread pool to avoid blocking
        the event loop.
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(C.thread_pool, self.execute)
