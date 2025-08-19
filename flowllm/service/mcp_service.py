from typing import Dict, Optional

from fastmcp import FastMCP
from pydantic import BaseModel, create_model, Field

from flowllm.context.service_context import C
from flowllm.schema.tool_call import ParamAttrs
from flowllm.service.base_service import BaseService
from flowllm.utils.common_utils import snake_to_camel


@C.register_service("mcp")
class MCPService(BaseService):
    TYPE_MAPPING = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp = FastMCP("FlowLLM")

    def _create_pydantic_model(self, flow_name: str, input_schema: Dict[str, ParamAttrs]) -> BaseModel:
        fields = {}

        for param_name, param_config in input_schema.items():
            field_type = self.TYPE_MAPPING.get(param_config.type, str)

            if not param_config.required:
                fields[param_name] = (Optional[field_type], Field(default=None, description=param_config.description))
            else:
                fields[param_name] = (field_type, Field(default=..., description=param_config.description))

        return create_model(f"{snake_to_camel(flow_name)}Model", **fields)

    def register_flow(self, flow_name: str):
        flow_config = self.flow_dict[flow_name]
        model_class = self._create_pydantic_model(flow_name=flow_name, input_schema=flow_config.input_schema)

        @self.mcp.tool(
            name=flow_name,
            description=flow_config.description,
            output_schema=flow_config.output_schema if flow_config.output_schema else None)
        def execute_flow_wrapper(request: model_class):
            return self.execute_flow(flow_name=flow_name, request=request)

        return execute_flow_wrapper

    def register_all_flows(self):
        for flow_name in self.flow_dict.keys():
            self.register_flow(flow_name)

    def __call__(self):
        if self.mcp_config.transport == "sse":
            self.mcp.run(transport="sse", host=self.mcp_config.host, port=self.mcp_config.port)
        elif self.mcp_config.transport == "stdio":
            self.mcp.run(transport="stdio")
        else:
            raise ValueError(f"unsupported mcp transport: {self.mcp_config.transport}")
