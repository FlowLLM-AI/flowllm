import asyncio
from functools import partial

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool
from loguru import logger

from flowllm.context.service_context import C
from flowllm.service.base_service import BaseService


@C.register_service("mcp")
class MCPService(BaseService):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mcp = FastMCP("FlowLLM")

    def register_flow(self, flow_name: str):
        flow_config = self.flow_config_dict[flow_name]

        async def execute_flow_async(**kwargs) -> str:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                executor=C.thread_pool,
                func=partial(self.execute_flow, flow_name=flow_name, **kwargs))  # noqa
            return response.answer

        tool = FunctionTool(name=flow_name,  # noqa
                            description=flow_config.description,  # noqa
                            fn=execute_flow_async,
                            parameters=flow_config.input_schema)
        self.mcp.add_tool(tool)
        logger.info(f"register flow={flow_name}")

    def __call__(self):
        for flow_name in self.flow_config_dict:
            self.register_flow(flow_name)

        if self.mcp_config.transport == "sse":
            self.mcp.run(transport="sse", host=self.mcp_config.host, port=self.mcp_config.port)
        elif self.mcp_config.transport == "stdio":
            self.mcp.run(transport="stdio")
        else:
            raise ValueError(f"unsupported mcp transport: {self.mcp_config.transport}")
