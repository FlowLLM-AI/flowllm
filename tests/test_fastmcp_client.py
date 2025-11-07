"""Test script for FastMcpClient.

This script provides test functions for FastMcpClient class.
It can be run directly with: python test_fastmcp_client.py
"""

import asyncio
import os

from flowllm.core.utils.common_utils import load_env
from flowllm.core.utils.fastmcp_client import FastMcpClient

load_env()


async def main():
    """Test function to demonstrate FastMcpClient usage."""
    # Example 1: Using SSE HTTP connection
    # config = {
    #     "type": "sse",
    #     "url": "http://11.160.132.45:8010/sse",
    #     "headers": {},
    # }
    #
    # async with FastMcpClient("mcp", config) as client:
    #     tool_calls = await client.list_tool_calls()
    #     for tool_call in tool_calls:
    #         print(tool_call.model_dump_json())
    #
    #     result = await client.call_tool("ant_search", arguments={"query": "半导体行业PE中位数", "entity": "半导体"})
    #     print(result)

    # Example 2: Using stdio connection
    # config = {
    #     "command": "npx",
    #     "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    # }
    # async with FastMcpClient("mcp", config) as client:
    #     tools = await client.list_tools()
    #     tool_calls = await client.list_tool_calls()
    #     for tool_call in tool_calls:
    #         print(tool_call.simple_input_dump())

    # Example 3: Using SSE HTTP connection
    config = {
        "type": "sse",
        "url": "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse",
        "headers": {
            "Authorization": f"Bearer {os.getenv('FLOW_BAILIAN_API_KEY')}",
        },
    }

    async with FastMcpClient("mcp", config) as client:
        tool_calls = await client.list_tool_calls()
        tool_call = None
        for tool_call in tool_calls:
            print(tool_call.model_dump_json())

        if tool_call is not None:
            result = await client.call_tool(tool_call.name, arguments={"query": "半导体行业PE中位数"})
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
