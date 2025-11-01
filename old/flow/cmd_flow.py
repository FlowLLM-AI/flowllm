from flowllm.flow.base_flow import BaseFlow
from flowllm.flow.expression_parser import ExpressionParser


class CmdFlow(BaseFlow):

    def __init__(self, flow: str = "", **kwargs):
        super().__init__(**kwargs)
        self.flow = flow
        assert flow, "add `flow=<op_flow>` in cmd!"

    def build_flow(self):
        parser = ExpressionParser(self.flow)
        return parser.parse_flow()
