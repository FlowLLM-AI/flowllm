from typing import Dict, Any, List, Optional

from fastmcp import Client
from loguru import logger
from mcp.types import CallToolResult, Tool


class MCPClient:
    """Client for interacting with FlowLLM MCP service"""

    def __init__(self, transport: str = "sse", host: str = "0.0.0.0", port: int = 8001):
        """
        Initialize MCP client
        
        Args:
            transport: Transport type ("sse" or "stdio")
            host: Host address for SSE transport
            port: Port number for SSE transport
        """
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
            self.client = Client("stdio")
        else:
            self.client = Client(self.connection_url)

        await self.client.__aenter__()
        logger.info(f"Connected to MCP service at {self.connection_url}")

    async def disconnect(self):
        if self.client:
            await self.client.__aexit__(None, None, None)
            self.client = None

    async def list_tools(self) -> List[Tool]:
        tools = await self.client.list_tools()
        logger.info(f"Found {len(tools)} available tools")
        return tools

    async def get_tool(self, tool_name: str) -> Optional[Tool]:
        tools = await self.list_tools()
        for tool in tools:
            if tool.name == tool_name:
                return tool
        return None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        return await self.client.call_tool(tool_name, arguments=arguments)
