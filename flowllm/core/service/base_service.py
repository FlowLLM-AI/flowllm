"""Service base definitions for FlowLLM.

This module defines the abstract `BaseService` that concrete services (CLI, HTTP,
MCP, etc.) extend to integrate registered flows and run the application.
"""

from abc import ABC

from loguru import logger

from ..context import C
from ..flow import BaseFlow, BaseToolFlow
from ..schema import ServiceConfig


class BaseService(ABC):
    """Abstract base class for all services.

    Services are responsible for integrating registered flows into a runtime
    (e.g., CLI, HTTP server, MCP) and then starting that runtime.
    """

    def __init__(self, service_config: ServiceConfig):
        """Initialize the service.

        - service_config: The configuration object for the current service mode.
        """
        self.service_config: ServiceConfig = service_config

    def integrate_flow(self, _flow: BaseFlow) -> bool:
        """Integrate a standard flow into the service.

        Return True if the flow was integrated and should be logged; False
        otherwise. Default implementation does nothing.
        """
        return False

    def integrate_tool_flow(self, _flow: BaseToolFlow) -> bool:
        """Integrate a tool-callable flow into the service.

        Return True if the tool flow was integrated; False otherwise.
        """
        return False

    def integrate_stream_flow(self, _flow: BaseFlow) -> bool:
        """Integrate a streaming flow into the service.

        Return True if the streaming flow was integrated; False otherwise.
        """
        return False

    def run(self):
        """Integrate all registered flows and start the service runtime.

        Iterates over registered flows, integrates them according to type, then
        prints the logo (optional) and suppresses deprecation warnings. Concrete
        services should call super().run() before their own startup logic.
        """
        flow_names = []
        for _, flow in C.flow_dict.items():
            assert isinstance(flow, BaseFlow)
            if flow.stream:
                if self.integrate_stream_flow(flow):
                    flow_names.append(flow.name)

            elif isinstance(flow, BaseToolFlow):
                if self.integrate_tool_flow(flow):
                    flow_names.append(flow.name)

            else:
                if self.integrate_flow(flow):
                    flow_names.append(flow.name)

        logger.info(f"integrate {','.join(flow_names)}")

        import warnings

        warnings.filterwarnings("ignore", category=DeprecationWarning)
