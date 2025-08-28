from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.op.gallery import Mock1Op, Mock2Op, Mock3Op, Mock4Op, Mock5Op, Mock6Op
from flowllm.schema.tool_call import ToolCall, ParamAttrs


@C.register_tool_flow()
class MockToolFlow(BaseToolFlow):

    def build_flow(self):
        mock1_op = Mock1Op()
        mock2_op = Mock2Op()
        mock3_op = Mock3Op()
        mock4_op = Mock4Op()
        mock5_op = Mock5Op()
        mock6_op = Mock6Op()

        op = mock1_op >> ((mock4_op >> mock2_op) | mock5_op) >> (mock3_op | mock6_op)
        return op

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**{
            "index": 0,
            "id": "call_mock_tool_12345",
            "type": "function",
            "name": "mock_data_processor",
            "description": "A mock tool that processes data through multiple operations and returns structured results",
            "input_schema": {
                "input_data": ParamAttrs(
                    type="string",
                    description="The input data to be processed",
                    required=True
                ),
                "processing_mode": ParamAttrs(
                    type="string",
                    description="Processing mode: basic, advanced, or expert",
                    required=False
                ),
                "output_format": ParamAttrs(
                    type="string",
                    description="Output format: json, xml, or plain",
                    required=False
                )
            },
            "output_schema": {
                "result": ParamAttrs(
                    type="object",
                    description="Processed result data",
                    required=True
                ),
                "status": ParamAttrs(
                    type="string",
                    description="Processing status: success, warning, or error",
                    required=True
                ),
                "metadata": ParamAttrs(
                    type="object",
                    description="Additional metadata about the processing",
                    required=False
                )
            }
        })
