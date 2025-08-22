import asyncio
from functools import partial

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from flowllm.context.service_context import C
from flowllm.flow.base_tool_flow import BaseToolFlow
from flowllm.service.base_service import BaseService


@C.register_service("mcp")
class MCPService(BaseService):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp = FastMCP(name="FlowLLM")

    def integrate_tool_flow(self, tool_flow_name: str):
        tool_flow: BaseToolFlow = C.get_tool_flow(tool_flow_name)

        async def execute_flow_async(**kwargs) -> str:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                executor=C.thread_pool,
                func=partial(tool_flow.__call__, **kwargs))  # noqa
            return response.answer

        tool = FunctionTool(name=flow_name,  # noqa
                            description=tool_flow.tool_call.description,  # noqa
                            fn=execute_flow_async,
                            parameters=tool_flow.tool_call.input_schema)
        self.mcp.add_tool(tool)

    def __call__(self):
        self.integrate_tool_flows()

        if self.mcp_config.transport == "sse":
            self.mcp.run(transport="sse", host=self.mcp_config.host, port=self.mcp_config.port)
        elif self.mcp_config.transport == "stdio":
            self.mcp.run(transport="stdio")
        else:
            raise ValueError(f"unsupported mcp transport: {self.mcp_config.transport}")
