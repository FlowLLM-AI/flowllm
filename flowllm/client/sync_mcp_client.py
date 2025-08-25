import asyncio
from typing import Dict, Any, List, Optional

from mcp.types import CallToolResult, Tool

from flowllm.client import MCPClient


class SyncMCPClient:
    """Synchronous wrapper for MCPClient"""

    def __init__(self, transport: str = "sse", host: str = "0.0.0.0", port: int = 8001):
        """
        Initialize synchronous MCP client

        This client wraps the asynchronous MCPClient to provide a synchronous interface.
        It manages its own event loop for executing async operations synchronously.

        Args:
            transport: Transport type ("sse" or "stdio")
            host: Host address for SSE transport
            port: Port number for SSE transport
        """
        self.async_client = MCPClient(transport, host, port)  # Create underlying async client
        self._loop: asyncio.AbstractEventLoop | None = None  # Event loop for async operations

    def __enter__(self):
        """
        Context manager entry - sets up event loop and connects to MCP service
        
        Creates a new event loop, establishes connection to the MCP service,
        and returns self for use in 'with' statements.
        
        Returns:
            self for context manager usage
        """
        self._loop = asyncio.new_event_loop()  # Create new event loop for this client
        asyncio.set_event_loop(self._loop)  # Set as current event loop
        self._loop.run_until_complete(self.async_client.connect())  # Connect synchronously
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit - disconnects from MCP service and cleans up event loop
        
        Ensures proper cleanup by disconnecting from the MCP service and
        closing the event loop.
        """
        if self._loop:
            self._loop.run_until_complete(self.async_client.disconnect())  # Disconnect synchronously
            self._loop.close()  # Close the event loop
            self._loop = None  # Reset loop reference

    def _run_async(self, coro):
        """
        Execute an async coroutine synchronously using the managed event loop
        
        Args:
            coro: Coroutine to execute
            
        Returns:
            Result of the coroutine execution
            
        Raises:
            RuntimeError: If client is not connected (no event loop available)
        """
        if not self._loop:
            raise RuntimeError("Client not connected. Use context manager first.")
        return self._loop.run_until_complete(coro)  # Run coroutine to completion

    def list_tools(self) -> List[Tool]:
        """
        Synchronously retrieve list of available tools from the MCP service
        
        Returns:
            List of Tool objects representing available MCP tools
            
        Raises:
            RuntimeError: If client is not connected
            ConnectionError: If communication with MCP service fails
        """
        return self._run_async(self.async_client.list_tools())

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Synchronously get a specific tool by name from the MCP service
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            Tool object if found, None otherwise
            
        Raises:
            RuntimeError: If client is not connected
            ConnectionError: If communication with MCP service fails
        """
        return self._run_async(self.async_client.get_tool(tool_name))

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """
        Synchronously execute a tool on the MCP service with the provided arguments
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of arguments to pass to the tool
            
        Returns:
            CallToolResult containing the tool execution results
            
        Raises:
            RuntimeError: If client is not connected
            ValueError: If tool_name is invalid or arguments are malformed
            ConnectionError: If communication with MCP service fails
        """
        return self._run_async(self.async_client.call_tool(tool_name, arguments))
