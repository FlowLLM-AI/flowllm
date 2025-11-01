import asyncio
import os
from typing import Dict, Any, List, Optional

from fastmcp import Client
from fastmcp.client.transports import SSETransport, StreamableHttpTransport
from loguru import logger
from mcp.types import CallToolResult, Tool

from flowllm.schema.tool_call import ToolCall


class FastmcpClient:

    def __init__(
        self,
        name: str,
        config: dict,
        max_retries: int = 3,
        timeout: Optional[float] = None,
    ):
        """
        Initialize FastMCP client with configuration similar to McpClient.

        Args:
            name: Client name for logging
            config: Configuration dict with keys:
                - type: "sse", "streamable_http", "streamableHttp", or "stdio" (default: "sse")
                - url: URL for HTTP connection (e.g., "http://host:port/sse")
                - headers: Optional dict of HTTP headers (supports env var formatting like "{API_KEY}")
                - timeout: Optional timeout for requests (seconds)
                - sse_read_timeout: Optional SSE read timeout (seconds)
            max_retries: Maximum number of retry attempts
            timeout: Default timeout for operations
        """
        self.name: str = name
        self.config: dict = config
        self.max_retries: int = max_retries
        self.timeout: Optional[float] = timeout

        self.client: Client | None = None

    async def astart(self):
        """Start and initialize the client connection."""
        transport_type = self.config.get("type", "sse")

        if transport_type == "stdio":
            # For stdio, FastMCP will infer the transport from the URL
            self.client = Client("stdio", name=self.name, timeout=self.timeout)
        else:
            # Build URL from config
            url = self.config.get("url")
            if not url:
                raise ValueError("URL is required for HTTP transport")

            # Process headers if provided
            headers = None
            if self.config.get("headers"):
                headers = {}
                for key, value in self.config["headers"].items():
                    if isinstance(value, str) and "{" in value:
                        # Format environment variables in headers (e.g., "Bearer {API_KEY}")
                        headers[key] = value.format(**os.environ)
                    else:
                        headers[key] = value

            # Get optional timeouts
            sse_read_timeout = self.config.get("sse_read_timeout")

            # Create appropriate transport based on type
            if transport_type in ["streamable_http", "streamableHttp"]:
                transport = StreamableHttpTransport(
                    url=url,
                    headers=headers,
                    sse_read_timeout=sse_read_timeout,
                )
            else:  # Default to SSE
                transport = SSETransport(
                    url=url,
                    headers=headers,
                    sse_read_timeout=sse_read_timeout,
                )

            # Create client with custom transport
            self.client = Client(transport, name=self.name, timeout=self.timeout)

        await self.client.__aenter__()
        logger.info(f"{self.name} connected to MCP service")

    async def __aenter__(self) -> "FastmcpClient":
        """Context manager entry with retry logic."""
        for i in range(self.max_retries):
            try:
                if self.timeout is not None:
                    await asyncio.wait_for(self.astart(), timeout=self.timeout)
                else:
                    await self.astart()
                break

            except asyncio.TimeoutError:
                logger.exception(f"{self.name} start timeout after {self.timeout}s")

                if self.client:
                    try:
                        await self.client.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self.client = None

                if i == self.max_retries - 1:
                    raise TimeoutError(f"{self.name} start timeout after {self.timeout}s")

                await asyncio.sleep(1 + i)

            except Exception as e:
                logger.exception(
                    f"{self.name} start failed with {e}. " f"Retry {i + 1}/{self.max_retries} in {1 + i}s...",
                )

                if self.client:
                    try:
                        await self.client.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self.client = None

                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1:
                    break

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with retry logic."""
        for i in range(self.max_retries):
            try:
                if self.client:
                    await self.client.__aexit__(None, None, None)
                    self.client = None
                break

            except Exception as e:
                logger.exception(
                    f"{self.name} close failed with {e}. " f"Retry {i + 1}/{self.max_retries} in {1 + i}s...",
                )
                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1:
                    break

    async def list_tools(self) -> List[Tool]:
        """List all available tools with retry logic."""
        if not self.client:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools = []
        for i in range(self.max_retries):
            try:
                if self.timeout is not None:
                    tools = await asyncio.wait_for(
                        self.client.list_tools(),
                        timeout=self.timeout,
                    )
                else:
                    tools = await self.client.list_tools()
                break

            except asyncio.TimeoutError:
                logger.exception(f"{self.name} list tools timeout after {self.timeout}s")

                if i == self.max_retries - 1:
                    raise TimeoutError(f"{self.name} list tools timeout after {self.timeout}s")

                await asyncio.sleep(1 + i)

            except Exception as e:
                logger.exception(
                    f"{self.name} list tools failed with {e}. " f"Retry {i + 1}/{self.max_retries} in {1 + i}s...",
                )
                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1:
                    raise e

        logger.info(f"{self.name} found {len(tools)} available tools")
        return tools

    async def list_tool_calls(self) -> List[ToolCall]:
        """List all available tools as ToolCall objects."""
        if not self.client:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools = await self.list_tools()
        return [ToolCall.from_mcp_tool(t) for t in tools]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """Call a tool with retry logic."""
        if not self.client:
            raise RuntimeError(f"Server {self.name} not initialized")

        result = None
        for i in range(self.max_retries):
            try:
                if self.timeout is not None:
                    result = await asyncio.wait_for(
                        self.client.call_tool(tool_name, arguments=arguments),
                        timeout=self.timeout,
                    )
                else:
                    result = await self.client.call_tool(tool_name, arguments=arguments)
                break

            except asyncio.TimeoutError:
                logger.exception(f"{self.name}.{tool_name} call_tool timeout after {self.timeout}s")

                if i == self.max_retries - 1:
                    raise TimeoutError(f"{self.name}.{tool_name} call_tool timeout after {self.timeout}s")

                await asyncio.sleep(1 + i)

            except Exception as e:
                logger.exception(
                    f"{self.name}.{tool_name} call_tool failed with {e}. "
                    f"Retry {i + 1}/{self.max_retries} in {1 + i}s...",
                )
                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1:
                    raise e

        return result


async def main():
    """Example usage matching McpClient pattern."""
    # Example 1: SSE transport with headers and environment variable formatting
    config = {
        "type": "sse",
        "url": "http://localhost:8001/sse",
        "headers": {
            "Authorization": "Bearer {API_KEY}",  # Will be formatted from environment
            "X-Custom-Header": "custom-value",
        },
        "timeout": 30.0,
        "sse_read_timeout": 60.0,
    }

    async with FastmcpClient("fastmcp", config, max_retries=3) as client:
        tool_calls = await client.list_tool_calls()
        for tool_call in tool_calls:
            print(tool_call.model_dump_json())

        # Call a tool
        # result = await client.call_tool("search", {"query": "test"})
        # print(result)

    # Example 2: Streamable HTTP transport (compatible with McpClient config)
    config2 = {
        "type": "streamable_http",
        "url": "http://11.160.132.45:8010/sse",
        "headers": {},
    }

    async with FastmcpClient("mcp", config2) as client:
        tools = await client.list_tools()
        print(f"Found {len(tools)} tools")


if __name__ == "__main__":
    asyncio.run(main())
