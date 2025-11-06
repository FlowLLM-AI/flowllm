"""Service base definitions for FlowLLM.

This module defines the abstract `BaseService` that concrete services (CLI, HTTP,
MCP, etc.) extend to integrate registered flows and run the application.
"""

import os
from abc import ABC

from loguru import logger

from ..context import C
from ..flow import BaseFlow, BaseToolFlow
from ..schema import ServiceConfig
from ..utils import print_logo


class BaseService(ABC):
    """Abstract base class for all services.

    Services are responsible for integrating registered flows into a runtime
    (e.g., CLI, HTTP server, MCP) and then starting that runtime.
    """

    def __init__(self, service_config: ServiceConfig, enable_logo: bool = True):
        """Initialize the service.

        - service_config: The configuration object for the current service mode.
        - enable_logo: Whether to print the ASCII logo on startup.
        """
        self.service_config: ServiceConfig = service_config
        self.enable_logo: bool = enable_logo

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
        for _, flow in C.flow_dict.items():
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
            print_logo(service_config=self.service_config, app_name=os.getenv("APP_NAME"))

        import warnings

        warnings.filterwarnings("ignore", category=DeprecationWarning)
