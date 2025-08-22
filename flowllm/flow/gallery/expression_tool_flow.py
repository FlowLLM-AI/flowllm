from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.flow.parser.expression_parser import ExpressionParser
from flowllm.schema.service_config import FlowConfig
from flowllm.schema.tool_call import ToolCall


class ExpressionToolFlow(BaseToolFlow):

    def __init__(self, flow_config: FlowConfig = None, **kwargs):
        super().__init__(name=flow_config.name, **kwargs)
        self.flow_config: FlowConfig = flow_config
        self.parser = ExpressionParser(flow_config.flow_content)

    def build_flow(self):
        return self.parser.parse_flow()

    def build_tool_call(self) -> ToolCall:
        return ToolCall(**self.flow_config.model_dump())
