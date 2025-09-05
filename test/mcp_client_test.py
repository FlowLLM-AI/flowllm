import asyncio
import json
from typing import Dict, Any, List

from mcp.types import CallToolResult, Tool
from loguru import logger

from flowllm.client.mcp_client import MCPClient


async def health_check(client: MCPClient) -> bool:
    """Test MCP connection by trying to list tools"""
    try:
        tools = await client.list_tools()
        return True
    except Exception as e:
        logger.error(f"MCP health check failed: {e}")
        return False


async def main():
    async with MCPClient(transport="sse", host="0.0.0.0", port=8001) as client:

        # Test 1: Health check
        print("=" * 50)
        print("Testing MCP connection...")
        try:
            is_healthy = await health_check(client)
            print(f"MCP connection status: {'OK' if is_healthy else 'Failed'}")
        except Exception as e:
            print(f"Health check failed: {e}")

        # Test 2: Get available tools
        print("=" * 50)
        print("Getting available MCP tools...")
        try:
            tools = await client.list_tools()
            if tools:
                print(f"Found {len(tools)} available tools:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description}")
            else:
                print("No tools found or failed to retrieve tools")
        except Exception as e:
            print(f"Failed to get tools: {e}")

        # Test queries
        query1 = "阿里巴巴怎么样？"
        query2 = "寒武纪还可以买吗？"

        # Test 3: Execute various MCP tools (similar to HTTP test)
        test_cases = [
            # ("ant_search", {"query": "阿里巴巴怎么样？", "entity": "阿里巴巴"}),
            ("ant_investment", {"entity": "阿里巴巴", "analysis_category": "股票"}),
            # ("dashscope_search_tool_flow", {"query": "阿里巴巴怎么样？"}),
            # ("get_a_stock_infos", {"query": query2}),
            # ("get_a_stock_news", {"query": query2}),

            # ("mock_tool_flow", {"a": query2}),
            # ("mock_async_tool_flow", {"a": query2}),
            # ("tavily_search_tool_flow", {"query": query2}),
        ]

        for tool_name, arguments in test_cases:
            print("=" * 50)
            print(f"Testing tool: {tool_name}")
            try:
                result = await client.call_tool(tool_name, arguments)
                if result.content:
                    print(f"Result content: {result.content[0].text}")
                if hasattr(result, 'structured_content') and result.structured_content:
                    print(f"Structured content: {json.dumps(result.structured_content, indent=2, ensure_ascii=False)}")
                print("✓ Tool call successful")
            except Exception as e:
                print(f"✗ Tool call failed: {e}")


if __name__ == "__main__":
    print("FlowLLM MCP Client Test")
    print("Make sure the MCP service is running on http://0.0.0.0:8001")
    print("You can start it with: python -m flowllm.app --backend mcp")
    print()

    asyncio.run(main())
