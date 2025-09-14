from abc import ABC

from loguru import logger

from flowllm.context.service_context import C
from flowllm.flow import BaseFlow, BaseToolFlow
from flowllm.schema.service_config import ServiceConfig
from flowllm.utils.logo_utils import print_logo


class BaseService(ABC):

    def __init__(self, service_config: ServiceConfig, enable_logo: bool = True):
        self.service_config: ServiceConfig = service_config
        self.enable_logo: bool = enable_logo

    def integrate_flow(self, flow: BaseFlow) -> bool:
        return False

    def integrate_tool_flow(self, flow: BaseToolFlow) -> bool:
        return False

    def integrate_stream_flow(self, flow: BaseFlow) -> bool:
        return False

    def run(self):
        for name, flow in C.flow_dict.items():
            assert isinstance(flow, BaseFlow)
            if flow.stream:
                if self.integrate_stream_flow(flow):
                    logger.info(f"integrate stream flow={flow.name}")

            elif isinstance(flow, BaseToolFlow):
                if self.integrate_tool_flow(flow):
                    logger.info(f"integrate tool flow={flow.name}")

            else:
                if self.integrate_flow(flow):
                    logger.info(f"integrate flow={flow.name}")

        if self.enable_logo:
            print_logo(service_config=self.service_config)

        import warnings

        warnings.filterwarnings("ignore", category=DeprecationWarning)
        ...