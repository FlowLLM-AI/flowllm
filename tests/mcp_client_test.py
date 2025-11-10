"""Test module for FastMcpClient functionality.

This module contains tests and examples demonstrating the usage of FastMcpClient
for interacting with MCP (Model Context Protocol) servers, including listing
available tools and calling MCP tools with arguments.
"""

import asyncio
import json

from loguru import logger

from flowllm.core.utils import FastMcpClient


async def main():
    """Test function for FastMcpClient.

    This function demonstrates how to use FastMcpClient to:
    - List available MCP tools
    - Call MCP tools with arguments
    - Handle tool results and errors
    """
    # New config-based interface matching McpClient
    config = {
        "type": "sse",
        "url": "http://0.0.0.0:8001/sse",
        "headers": {},
        "timeout": 30.0,
    }

    async with FastMcpClient("test_client", config, max_retries=3) as client:

        print("=" * 50)
        print("Getting available MCP tools...")
        try:
            tool_calls = await client.list_tool_calls()
            if tool_calls:
                for tool_call in tool_calls:
                    print(tool_call.simple_input_dump())
            else:
                print("No tools found or failed to retrieve tools")
        except Exception as e:
            print(f"Failed to get tools: {e}")

        query = "阿里巴巴前景怎么样？"

        test_cases = [
            ("demo_mcp_flow", {"query": query}),
        ]

        for tool_name, arguments in test_cases:
            print("=" * 50)
            print(f"Testing tool: {tool_name} with arguments={arguments}")
            try:
                # New interface: call_tool(tool_name, arguments) returns CallToolResult
                result = await client.call_tool(tool_name, arguments)
                print(f"Tool result: {result}")

                if result.content:
                    print(f"Result content: {result.content[0].text}")
                if result.structured_content:
                    print(f"Structured content: {json.dumps(result.structured_content, indent=2, ensure_ascii=False)}")
                if result.is_error:
                    print(f"⚠ Tool returned error: {result.content[0].text if result.content else 'Unknown error'}")
                else:
                    print("✓ Tool call successful")

            except Exception as e:
                logger.exception(e)
                print(f"✗ Tool call failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
