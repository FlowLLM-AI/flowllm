import asyncio
import json

from flowllm.client.mcp_client import MCPClient


async def main():
    async with MCPClient(transport="sse", host="0.0.0.0", port=8001) as client:

        print("=" * 50)
        print("Getting available MCP tools...")
        try:
            tool_calls = await client.list_tool_calls()
            if tool_calls:
                for tool_call in tool_calls:
                    print(json.dumps(tool_call, ensure_ascii=False))
            else:
                print("No tools found or failed to retrieve tools")
        except Exception as e:
            print(f"Failed to get tools: {e}")

        query1 = "阿里巴巴怎么样？"
        # query2 = "寒武纪还可以买吗？"
        query2 = "寒武纪"

        test_cases = [
            # ("ant_search", {"query": "阿里巴巴怎么样？", "entity": "阿里巴巴"}),
            ("ant_investment", {"entity": "阿里巴巴", "analysis_category": "股票"}),
            # ("dashscope_search_tool_flow", {"query": "阿里巴巴怎么样？"}),
            # ("get_a_stock_infos", {"query": query2}),
            # ("get_a_stock_news", {"query": query2}),
            # ("tavily_search_tool_flow", {"query": query2}),

            # ("mock_tool_flow", {"a": query2}),
            # ("mock_async_tool_flow", {"a": query2}),
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
