import asyncio
from typing import Dict, Any, List, Optional

from mcp.types import CallToolResult, Tool

from flowllm.client import MCPClient


class SyncMCPClient:
    """Synchronous wrapper for MCPClient"""

    def __init__(self, transport: str = "sse", host: str = "0.0.0.0", port: int = 8001):
        """
        Initialize synchronous MCP client

        Args:
            transport: Transport type ("sse" or "stdio")
            host: Host address for SSE transport
            port: Port number for SSE transport
        """
        self.async_client = MCPClient(transport, host, port)
        self._loop: asyncio.AbstractEventLoop | None = None

    def __enter__(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.async_client.connect())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._loop:
            self._loop.run_until_complete(self.async_client.disconnect())
            self._loop.close()
            self._loop = None

    def _run_async(self, coro):
        if not self._loop:
            raise RuntimeError("Client not connected. Use context manager first.")
        return self._loop.run_until_complete(coro)

    def list_tools(self) -> List[Tool]:
        return self._run_async(self.async_client.list_tools())

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        return self._run_async(self.async_client.get_tool(tool_name))

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        return self._run_async(self.async_client.call_tool(tool_name, arguments))
