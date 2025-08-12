from abc import ABC

from flowllm.context.flow_context import FlowContext


class BaseFlowEngine(ABC):

    def __init__(self,
                 flow_name: str,
                 flow_content: str,
                 flow_context: FlowContext):
        self.flow_name: str = flow_name
        self.flow_content: str = flow_content
        self.flow_context: FlowContext = flow_context

    def _parse_flow(self):
        raise NotImplementedError

    def _print_flow(self):
        raise NotImplementedError

    def _execute_flow(self):
        raise NotImplementedError

    def execute(self):
        ...
