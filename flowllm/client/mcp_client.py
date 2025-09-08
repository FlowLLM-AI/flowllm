from typing import Dict, Any, List, Optional

from fastmcp import Client
from loguru import logger
from mcp.types import CallToolResult, Tool

from flowllm.schema.tool_call import ToolCall


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

        # Configure connection URL based on transport type
        if transport == "sse":
            # Server-Sent Events transport over HTTP
            self.connection_url = f"http://{host}:{port}/sse/"
        elif transport == "stdio":
            # Standard input/output transport for local processes
            self.connection_url = "stdio"
        else:
            raise ValueError(f"Unsupported transport: {transport}")

        self.client: Client | None = None  # MCP client instance, initialized on connect

    async def __aenter__(self):
        """Async context manager entry - automatically connects to MCP service"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures proper cleanup and disconnection"""
        await self.disconnect()

    async def connect(self):
        """
        Establish connection to the MCP service
        
        Creates and initializes the MCP client based on the configured transport type.
        For stdio transport, connects to a local process. For SSE transport, connects
        to the HTTP endpoint.
        
        Raises:
            ConnectionError: If unable to connect to the MCP service
        """
        if self.transport == "stdio":
            self.client = Client("stdio")  # Connect to stdio-based MCP server
        else:
            self.client = Client(self.connection_url)  # Connect to HTTP-based MCP server

        await self.client.__aenter__()  # Initialize the client connection
        logger.info(f"Connected to MCP service at {self.connection_url}")

    async def disconnect(self):
        """
        Disconnect from the MCP service and clean up resources
        
        Safely closes the MCP client connection and resets the client instance.
        """
        if self.client:
            await self.client.__aexit__(None, None, None)  # Properly close the client connection
            self.client = None  # Reset client reference

    async def list_tools(self) -> List[Tool]:
        """
        Retrieve list of available tools from the MCP service
        
        Returns:
            List of Tool objects representing available MCP tools
            
        Raises:
            RuntimeError: If client is not connected
            ConnectionError: If communication with MCP service fails
        """
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first or use context manager.")
        
        tools = await self.client.list_tools()
        logger.info(f"Found {len(tools)} available tools")
        return tools

    async def list_tool_calls(self) -> List[dict]:
        tools = await self.list_tools()
        return [ToolCall.from_mcp_tool(t).simple_input_dump() for t in tools]

    async def get_tool(self, tool_name: str) -> Optional[Tool]:
        """
        Get a specific tool by name from the MCP service
        
        Args:
            tool_name: Name of the tool to retrieve
            
        Returns:
            Tool object if found, None otherwise
            
        Raises:
            RuntimeError: If client is not connected
            ConnectionError: If communication with MCP service fails
        """
        tools = await self.list_tools()  # Get all available tools
        
        # Search for the requested tool by name
        for tool in tools:
            if tool.name == tool_name:
                return tool
        return None  # Tool not found

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """
        Execute a tool on the MCP service with the provided arguments
        
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
        if not self.client:
            raise RuntimeError("Client not connected. Call connect() first or use context manager.")
            
        return await self.client.call_tool(tool_name, arguments=arguments)
