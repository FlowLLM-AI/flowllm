from flowllm.flow.base_flow import BaseFlow
from flowllm.flow.expression.expression_parser import ExpressionParser


class CmdFlow(BaseFlow):

    def __init__(self,
                 use_async: bool = False,
                 stream: bool = False,
                 service_type: str = "cmd",
                 **kwargs):
        super().__init__(use_async=use_async, stream=stream, service_type=service_type, **kwargs)

    def build_flow(self):
        flow: str = self.flow_params.get("flow", "")
        assert flow, "add `flow=<op_flow>` in cmd!"
        parser = ExpressionParser(flow)
        return parser.parse_flow()
