from typing import Dict, Any, List, Optional

from fastmcp import Client
from loguru import logger
from mcp.types import CallToolResult, Tool

from flowllm.schema.tool_call import ToolCall


class FastmcpClient:

    def __init__(self, transport: str = "sse", host: str = "0.0.0.0", port: int = 8001):
        self.transport = transport
        self.host = host
        self.port = port

        if transport == "sse":
            self.connection_url = f"http://{host}:{port}/sse/"
        elif transport == "stdio":
            self.connection_url = "stdio"
        else:
            raise ValueError(f"Unsupported transport: {transport}")

        self.client: Client | None = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def connect(self):
        if self.transport == "stdio":
            self.client = Client("stdio")  # Connect to stdio-based MCP server
        else:
            self.client = Client(self.connection_url)  # Connect to HTTP-based MCP server

        await self.client.__aenter__()  # Initialize the client connection
        logger.info(f"Connected to MCP service at {self.connection_url}")

    async def disconnect(self):
        if self.client:
            await self.client.__aexit__(None, None, None)  # Properly close the client connection
            self.client = None

    async def list_tools(self) -> List[Tool]:
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first or use context manager.")

        tools = await self.client.list_tools()
        logger.info(f"Found {len(tools)} available tools")
        return tools

    async def list_tool_calls(self) -> List[ToolCall]:
        tools = await self.list_tools()
        return [ToolCall.from_mcp_tool(t) for t in tools]

    async def get_tool(self, tool_name: str) -> Optional[Tool]:
        tools = await self.list_tools()  # Get all available tools
        for tool in tools:
            if tool.name == tool_name:
                return tool
        return None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first or use context manager.")

        return await self.client.call_tool(tool_name, arguments=arguments)
