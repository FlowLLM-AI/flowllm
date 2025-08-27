from abc import abstractmethod, ABC
from typing import Dict, Optional

from loguru import logger
from pydantic import create_model, Field

from flowllm.config.pydantic_config_parser import PydanticConfigParser
from flowllm.context.service_context import C
from flowllm.schema.flow_request import FlowRequest
from flowllm.schema.service_config import ServiceConfig
from flowllm.schema.tool_call import ParamAttrs
from flowllm.utils.common_utils import snake_to_camel


class BaseService(ABC):
    TYPE_MAPPING = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
    }

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

    def _create_pydantic_model(self, flow_name: str, input_schema: Dict[str, ParamAttrs]):
        fields = {}

        for param_name, param_config in input_schema.items():
            field_type = self.TYPE_MAPPING.get(param_config.type, str)

            if not param_config.required:
                fields[param_name] = (Optional[field_type], Field(default=None, description=param_config.description))
            else:
                fields[param_name] = (field_type, Field(default=..., description=param_config.description))

        return create_model(f"{snake_to_camel(flow_name)}Model", __base__=FlowRequest, **fields)

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
