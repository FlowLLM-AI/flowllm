import asyncio
import json

from loguru import logger

from flowllm.client.fastmcp_client import FastmcpClient


async def main():
    async with FastmcpClient(transport="sse", host="0.0.0.0", port=8001) as client:

        print("=" * 50)
        print("Getting available MCP tools...")
        try:
            tool_calls = await client.list_tool_calls()
            if tool_calls:
                for tool_call in tool_calls:
                    print(tool_call.model_dump_json())
            else:
                print("No tools found or failed to retrieve tools")
        except Exception as e:
            print(f"Failed to get tools: {e}")

        query1 = "阿里巴巴怎么样？"
        query2 = "寒武纪"

        test_cases = [
            # ("ant_search", {"query": "阿里巴巴怎么样？", "entity": "阿里巴巴"}),
            # ("ant_investment", {"entity": "阿里巴巴", "analysis_category": "股票"}),
            # ("dashscope_search", {"query": "阿里巴巴怎么样？"}),
            # ("get_a_stock_infos", {"query": query2}),
            # ("get_a_stock_news", {"query": query2}),
            # ("tavily_search", {"query": query2}),

            # ("mock_tool_flow", {"a": query2}),
            # ("mock_async_tool_flow", {"a": query2}),
            # ("tdx_wenda_quotes", {"question": "半导体行业PE中位数"}),
            # ("tdx_market_quotes", {"code": "000001", "setcode": "1"}),
            ("mock_exception", {"query": "run_time"}),
        ]

        for tool_name, arguments in test_cases:
            print("=" * 50)
            print(f"Testing tool: {tool_name}")
            try:
                # result = await client.call_tool(tool_name, arguments)
                result = await client.call_tool(tool_name, arguments, raise_on_error=False)
                print(f"Tool result: {result}")

                if result.content:
                    print(f"Result content: {result.content[0].text}")
                if hasattr(result, 'structured_content') and result.structured_content:
                    print(f"Structured content: {json.dumps(result.structured_content, indent=2, ensure_ascii=False)}")
                print("✓ Tool call successful")

            except Exception as e:
                logger.exception(e)
                print(f"✗ Tool call failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
