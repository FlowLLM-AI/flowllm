from flowllm.op.gallery.terminate_op import TerminateOp

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.schema.tool_call import ToolCall


@C.register_tool_flow()
class TerminateToolFlow(BaseToolFlow):

    def build_flow(self):
        return TerminateOp()

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "terminate",
            "description": "If you can answer the user's question based on the context, be sure to use the **terminate** tool.",
            "input_schema": {
                "status": {
                    "type": "str",
                    "description": "If the user's question can be answered, return success, otherwise return failure.",
                    "required": True,
                    "enum": ["success", "failure"],
                }
            }
        })

    def return_callback(self, context: FlowContext):
        context.response.answer = context.terminate_answer
        return context.response
