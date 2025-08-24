from abc import abstractmethod, ABC

from loguru import logger

from flowllm.config.pydantic_config_parser import PydanticConfigParser
from flowllm.context.service_context import C
from flowllm.schema.service_config import ServiceConfig


class BaseService(ABC):

    def __init__(self, service_config: ServiceConfig):
        self.service_config = service_config

        self.mcp_config = self.service_config.mcp
        self.http_config = self.service_config.http
        C.init_by_service_config(self.service_config)

    @classmethod
    def get_service(cls, *args, parser: type[PydanticConfigParser] = PydanticConfigParser) -> "BaseService":
        config_parser = parser(ServiceConfig)
        service_config: ServiceConfig = config_parser.parse_args(*args)
        service_cls = C.resolve_service(service_config.backend)
        return service_cls(service_config)

    def integrate_tool_flow(self, tool_flow_name: str):
        ...

    def integrate_tool_flows(self):
        for tool_flow_name in C.tool_flow_names:
            self.integrate_tool_flow(tool_flow_name)
            logger.info(f"integrate flow_endpoint={tool_flow_name}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...

    @abstractmethod
    def __call__(self):
        ...
