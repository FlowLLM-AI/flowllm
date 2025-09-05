from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.flow.expression.expression_parser import ExpressionParser
from flowllm.schema.service_config import FlowConfig
from flowllm.schema.tool_call import ToolCall


class ExpressionToolFlow(BaseToolFlow):

    def __init__(self, flow_config: FlowConfig = None, **kwargs):
        self.flow_config: FlowConfig = flow_config
        super().__init__(name=flow_config.name,
                         use_async=self.flow_config.use_async,
                         stream=self.flow_config.stream,
                         service_type=self.flow_config.service_type,
                         **kwargs)

    def build_flow(self):
        parser = ExpressionParser(self.flow_config.flow_content)
        return parser.parse_flow()

    def build_tool_call(self) -> ToolCall:
        if hasattr(self.flow_op, "tool_call"):
            return self.flow_op.tool_call
        else:
            return ToolCall(**self.flow_config.model_dump())
