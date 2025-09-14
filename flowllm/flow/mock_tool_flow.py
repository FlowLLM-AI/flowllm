from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.op.gallery.mock_op import Mock1Op, Mock2Op, Mock3Op, Mock4Op, Mock5Op, Mock6Op
from flowllm.schema.tool_call import ToolCall, ParamAttrs


@C.register_flow(register_app="FlowLLM")
class MockToolFlow(BaseToolFlow):

    def __init__(self, stream: bool = False, **kwargs):
        super().__init__(stream=stream, **kwargs)

    def build_flow(self):
        mock1_op = Mock1Op()
        mock2_op = Mock2Op()
        mock3_op = Mock3Op()
        return mock1_op >> ((mock2_op >> mock3_op) | mock1_op) >> (mock2_op | mock3_op)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "type": "function",
            "name": "mock_data",
            "description": "A mock tool that processes data through multiple operations and returns structured results",
            "input_schema": {
                "a": ParamAttrs(
                    type="string",
                    description="The input data to be processed",
                    required=True
                ),
                "b": ParamAttrs(
                    type="string",
                    description="Processing mode: basic, advanced, or expert",
                    required=False
                ),
            }
        })


@C.register_flow(register_app="FlowLLM")
class MockAsyncToolFlow(BaseToolFlow):

    def __init__(self, stream: bool = False, **kwargs):
        super().__init__(stream=stream, **kwargs)

    def build_flow(self):
        mock4_op = Mock4Op()
        mock5_op = Mock5Op()
        mock6_op = Mock6Op()
        return mock4_op >> ((mock5_op >> mock6_op) | mock4_op) >> (mock5_op | mock6_op)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "type": "function",
            "name": "mock_data",
            "description": "A mock tool that processes data through multiple operations and returns structured results",
            "input_schema": {
                "a": ParamAttrs(
                    type="string",
                    description="The input data to be processed",
                    required=True
                ),
                "b": ParamAttrs(
                    type="string",
                    description="Processing mode: basic, advanced, or expert",
                    required=False
                ),
            }
        })
