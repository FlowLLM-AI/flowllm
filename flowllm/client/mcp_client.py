import asyncio
import os
import shutil
from contextlib import AsyncExitStack
from typing import Any, List

import mcp.types
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from flowllm.schema.tool_call import ToolCall


class McpClient:

    def __init__(self, name: str, config: dict[str, Any], append_env: bool = False) -> None:
        self.name: str = name
        self.config: dict[str, Any] = config
        self.append_env: bool = append_env
        self.session: ClientSession | None = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def __aenter__(self) -> "McpClient":
        command = shutil.which("npx") if self.config.get("command") == "npx" else self.config.get("command")

        if command:
            env_params: dict = {}
            if self.append_env:
                env_params.update(os.environ)
            if self.config.get("env"):
                env_params.update(self.config["env"])

            server_params = StdioServerParameters(command=command, args=self.config.get("args", []), env=env_params)
            streams = await self._exit_stack.enter_async_context(stdio_client(server_params))

        else:
            if self.config.get("type") in ["streamable_http", "streamableHttp"]:
                streams = await self._exit_stack.enter_async_context(streamablehttp_client(
                    url=self.config["url"],
                    headers=self.config.get("headers"),
                    timeout=self.config.get("timeout", 30),
                    sse_read_timeout=self.config.get("sse_read_timeout", 300)))
                streams = (streams[0], streams[1])

            else:
                streams = await self._exit_stack.enter_async_context(sse_client(
                    url=self.config["url"],
                    headers=self.config.get("headers"),
                    timeout=self.config.get("timeout", 30),
                    sse_read_timeout=self.config.get("sse_read_timeout", 300)))

        session = await self._exit_stack.enter_async_context(ClientSession(*streams))
        await session.initialize()
        self.session = session
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._exit_stack.aclose()
        self.session = None

    async def list_tools(self) -> List[mcp.types.Tool]:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools_response = await self.session.list_tools()
        tools = [tool for item in tools_response if isinstance(item, tuple) and item[0] == "tools" for tool in item[1]]
        return tools

    async def list_tool_calls(self) -> List[ToolCall]:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools = await self.list_tools()
        return [ToolCall.from_mcp_tool(t) for t in tools]

    async def call_tool(self, tool_name: str, arguments: dict, retries: int = 3, delay: float = 0.1):
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0

        while attempt < retries:
            result = await self.session.call_tool(tool_name, arguments)
            if result:
                return result

            attempt += 1
            if attempt < retries:
                logger.warning(f"Tool={tool_name} execution failed. Retry {attempt}/{retries} in {delay}s...")
                await asyncio.sleep(delay)
        return None


async def main():
    config = {
        "type": "sse",
        # "url": "https://dashscope.aliyuncs.com/api/v1/mcps/finance-spirit/sse",
        "url": "https://dashscope.aliyuncs.com/api/v1/mcps/Gfsecurities-lhb/sse",
        "headers": {
            "Authorization": "Bearer sk-36ab308b8d2e4699b04af3a97cd1d5e6"
        }
    }
    # config = {
    #     "type": "sse",
    #     "url": "http://11.160.132.45:8010/sse",
    #     "headers": {}
    # }
    async with McpClient("mcp", config) as client:
        tool_calls = await client.list_tool_calls()
        for tool_call in tool_calls:
            print(tool_call.model_dump_json())
        # result = await client.call_tool()


if __name__ == "__main__":
    asyncio.run(main())
