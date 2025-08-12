from abc import ABC
from typing import Optional

from loguru import logger

from flowllm.context.flow_context import FlowContext
from flowllm.op.base_op import BaseOp


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
        ...

    def _print_flow(self):
        raise NotImplementedError

    def _execute_flow(self):
        raise NotImplementedError

    def __call__(self):
        result = None
        try:
            logger.info(f"\n========== Flow: {self.flow_name} start ==========")
            self._parse_flow()
            assert self._parsed_flow is not None, "flow_content is not parsed!"

            self._print_flow()
            result = self._execute_flow()

            logger.info(f"\n========== Flow: {self.flow_name} end ==========")

        except Exception as e:
            logger.exception(f"Flow execution encounter error={e.args}")

        return result
