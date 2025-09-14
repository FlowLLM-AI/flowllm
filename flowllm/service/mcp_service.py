import os

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.service.base_service import BaseService
from flowllm.utils.pydantic_utils import create_pydantic_model


@C.register_service("mcp")
class MCPService(BaseService):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mcp = FastMCP(name=os.environ["FLOW_APP_NAME"])

    def integrate_tool_flow(self, flow: BaseToolFlow) -> bool:
        request_model = create_pydantic_model(flow.name, flow.tool_call.input_schema)

        async def execute_tool(**kwargs) -> str:
            response = await flow.async_call(**request_model(**kwargs).model_dump())
            return response.answer

        # add tool
        tool_call_schema = flow.tool_call.simple_input_dump()
        parameters = tool_call_schema[tool_call_schema["type"]]["parameters"]
        tool = FunctionTool(name=flow.name,  # noqa
                            description=flow.tool_call.description,  # noqa
                            fn=execute_tool,
                            parameters=parameters)

        self.mcp.add_tool(tool)
        return True

    def run(self):
        super().run()
        mcp_config = self.service_config.mcp

        if mcp_config.transport == "sse":
            self.mcp.run(transport="sse", host=mcp_config.host, port=mcp_config.port, show_banner=False)
        elif mcp_config.transport == "http":
            self.mcp.run(transport="http", host=mcp_config.host, port=mcp_config.port, show_banner=False)
        elif mcp_config.transport == "stdio":
            self.mcp.run(transport="stdio", show_banner=False)
        else:
            raise ValueError(f"unsupported mcp transport: {mcp_config.transport}")
