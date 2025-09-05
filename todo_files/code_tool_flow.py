from flowllm.op.code.execute_code_op import ExecuteCodeOp

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.schema.tool_call import ToolCall


@C.register_tool_flow()
class CodeToolFlow(BaseToolFlow):

    def build_flow(self):
        return ExecuteCodeOp()

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "python_execute",
            "description": "Execute python code can be used in scenarios such as analysis or calculation, and the final result can be printed using the `print` function.",
            "input_schema": {
                "code": {
                    "type": "str",
                    "description": "code to be executed. Please do not execute any matplotlib code here.",
                    "required": True
                }
            }
        })

    def return_callback(self, context: FlowContext):
        context.response.answer = context.code_result
        return context.response

