from flowllm.op.search.dashscope_deep_research_op import DashscopeDeepResearchOp

from flowllm.context.flow_context import FlowContext
from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.schema.tool_call import ToolCall


@C.register_tool_flow()
class DeepSearchToolFlow(BaseToolFlow):

    def build_flow(self):
        return DashscopeDeepResearchOp()

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "name": "deep_search",
            "description": "Perform deep research on a topic using Dashscope's qwen-deep-research model. This tool will conduct multi-phase research including model questioning, web research, and result generation.",
            "input_schema": {
                "query": {
                    "type": "str",
                    "description": "Research topic or question",
                    "required": True
                }
            }
        })

    def return_callback(self, context: FlowContext):
        context.response.answer = context.dashscope_deep_research_result
        return context.response


if __name__ == "__main__":
    from flowllm.utils.common_utils import load_env

    load_env()

    flow = DeepSearchToolFlow()
    result = flow(query="中国电解铝行业值得投资吗，有哪些值得投资的标的，各个标的之间需要对比优劣势")
    print(result.answer)