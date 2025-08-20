from abc import ABC
from typing import Optional

from flowllm.context.flow_context import FlowContext
from flowllm.op.base_op import BaseOp
from flowllm.utils.timer import timer


class BaseFlowEngine(ABC):

    def __init__(self, flow_name: str, flow_content: str, flow_context: FlowContext):
        self.flow_name: str = flow_name
        self.flow_content: str = flow_content
        self.flow_context: FlowContext = flow_context

        self._parsed_flow: Optional[BaseOp] = None
        self._parsed_ops_cache = {}

    def _parse_flow(self):
        raise NotImplementedError

    def _create_op(self, op_name: str):
        raise NotImplementedError

    def _print_flow(self):
        raise NotImplementedError

    def _execute_flow(self):
        raise NotImplementedError

    def __call__(self):
        self._parse_flow()
        self._print_flow()
        return self._execute_flow()
