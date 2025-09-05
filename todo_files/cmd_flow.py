from flowllm.flow.base_flow import BaseFlow
from flowllm.flow.expression.expression_parser import ExpressionParser


class CmdFlow(BaseFlow):

    def build_flow(self):
        flow: str = self.flow_params["flow"]
        assert flow, "add `flow=<op_flow>` in cmd!"
        parser = ExpressionParser(flow)
        return parser.parse_flow()
