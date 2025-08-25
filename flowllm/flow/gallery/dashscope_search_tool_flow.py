from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.op.search import DashscopeSearchOp
from flowllm.schema.tool_call import ToolCall


@C.register_tool_flow()
class DashscopeSearchToolFlow(BaseToolFlow):

    def build_flow(self):
        return DashscopeSearchOp()

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "web_search",
            "description": "Use search keywords to retrieve relevant information from the internet. If there are multiple search keywords, please use each keyword separately to call this tool.",
            "input_schema": {
                "query": {
                    "type": "str",
                    "description": "search keyword",
                    "required": True
                }
            }
        })

    def return_callback(self, context: FlowContext):
        context.response.answer = context.dashscope_search_result
        return context.response
