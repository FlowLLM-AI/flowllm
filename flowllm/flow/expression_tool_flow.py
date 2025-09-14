from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.flow.expression_parser import ExpressionParser
from flowllm.schema.service_config import FlowConfig
from flowllm.schema.tool_call import ToolCall


class ExpressionToolFlow(BaseToolFlow):

    def __init__(self, flow_config: FlowConfig = None, **kwargs):
        self.flow_config: FlowConfig = flow_config
        super().__init__(name=flow_config.name, stream=self.flow_config.stream, **kwargs)

    def build_flow(self):
        parser = ExpressionParser(self.flow_config.flow_content)
        return parser.parse_flow()

    def build_tool_call(self) -> ToolCall:
        if hasattr(self.flow_op, "tool_call"):
            return self.flow_op.tool_call
        else:
            return ToolCall(name=self.flow_config.name,
                            description=self.flow_config.description,
                            input_schema=self.flow_config.input_schema)
