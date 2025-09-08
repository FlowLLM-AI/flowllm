from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from .base_service import BaseService
from ..context.service_context import C
from ..flow.base_tool_flow import BaseToolFlow


@C.register_service("mcp")
class MCPService(BaseService):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp = FastMCP(name="FlowLLM")

    def integrate_flow(self, tool_flow: BaseToolFlow):
        if "mcp" not in tool_flow.service_type:
            return

        request_model = self._create_pydantic_model(tool_flow.name, tool_flow.tool_call.input_schema)

        async def execute_tool(**kwargs) -> str:
            response = await tool_flow(**request_model(**kwargs).model_dump())
            return response.answer

        # tool_flow.tool_call.name
        tool_call_schema = tool_flow.tool_call.simple_input_dump()
        parameters = tool_call_schema[tool_call_schema["type"]]["parameters"]
        tool = FunctionTool(name=tool_flow.name,  # noqa
                            description=tool_flow.tool_call.description,  # noqa
                            fn=execute_tool,
                            parameters=parameters)
        self.mcp.add_tool(tool)

    def execute(self):
        if self.mcp_config.transport == "sse":
            self.mcp.run(transport="sse", host=self.mcp_config.host, port=self.mcp_config.port, show_banner=False)
        elif self.mcp_config.transport == "http":
            self.mcp.run(transport="http", host=self.mcp_config.host, port=self.mcp_config.port, show_banner=False)
        elif self.mcp_config.transport == "stdio":
            self.mcp.run(transport="stdio", show_banner=False)
        else:
            raise ValueError(f"unsupported mcp transport: {self.mcp_config.transport}")
