from flowllm.flow.base_flow import BaseFlow
from flowllm.flow.parser.expression_parser import ExpressionParser


class CmdFlow(BaseFlow):

    def build_flow(self):
        flow: str = self.flow_params["flow"]
        assert flow, "flow is empty!"
        parser = ExpressionParser(flow)
        return parser.parse_flow()
