import asyncio
import os
import shutil
from contextlib import AsyncExitStack
from typing import List

import mcp.types
from loguru import logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from flowllm.schema.tool_call import ToolCall


class McpClient:

    def __init__(self,
                 name: str,
                 config: dict,
                 append_env: bool = False,
                 max_retries: int = 3):

        self.name: str = name
        self.config: dict = config
        self.append_env: bool = append_env
        self.max_retries: int = max_retries

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
            kwargs = {"url": self.config["url"]}
            if self.config.get("headers"):
                headers = self.config.get("headers")
                if headers.get("Authorization"):
                    assert isinstance(headers["Authorization"], str)
                    headers["Authorization"] = headers["Authorization"].format(**os.environ)
                kwargs["headers"] = headers
            if "timeout" in self.config:
                kwargs["timeout"] = self.config["timeout"]
            if "sse_read_timeout" in self.config:
                kwargs["sse_read_timeout"] = self.config["sse_read_timeout"]

            if self.config.get("type") in ["streamable_http", "streamableHttp"]:
                streams = await self._exit_stack.enter_async_context(streamablehttp_client(**kwargs))
                streams = (streams[0], streams[1])
            else:
                streams = await self._exit_stack.enter_async_context(sse_client(**kwargs))

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

        tools = []
        for i in range(self.max_retries):
            try:
                tools_response = await self.session.list_tools()
                tools = [tool for item in tools_response \
                         if isinstance(item, tuple) and item[0] == "tools" for tool in item[1]]
                break

            except Exception as e:
                logger.warning(f"{self.name} list tools failed. Retry {i + 1}/{self.max_retries} in {1 + i}s...")
                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1:
                    raise e

        return tools

    async def list_tool_calls(self) -> List[ToolCall]:
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools = await self.list_tools()
        return [ToolCall.from_mcp_tool(t) for t in tools]

    async def call_tool(self, tool_name: str, arguments: dict):
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        result = None
        for i in range(self.max_retries):
            try:
                result = await self.session.call_tool(tool_name, arguments)
                break

            except Exception as e:
                logger.warning(
                    f"{self.name}.{tool_name} call_tool failed. Retry {i + 1}/{self.max_retries} in {1 + i}s...")
                await asyncio.sleep(1 + i)

                if i == self.max_retries - 1:
                    raise e

        return result


async def main():
    config = {
        "type": "sse",
        "url": "http://11.160.132.45:8010/sse",
        "headers": {}
    }

    async with McpClient("mcp", config) as client:
        tool_calls = await client.list_tool_calls()
        for tool_call in tool_calls:
            print(tool_call.model_dump_json())

        # result = await client.call_tool("search", arguments={"query": "半导体行业PE中位数", "entity": "半导体"})
        # print(result)

if __name__ == "__main__":
    asyncio.run(main())
