import asyncio
import json

from loguru import logger

from flowllm.client.fastmcp_client import FastmcpClient


async def main():
    # New config-based interface matching McpClient
    config = {
        "type": "sse",
        "url": "http://11.164.204.33:8001/sse",  # or "http://0.0.0.0:8001/sse"
        "headers": {},
        "timeout": 30.0
    }
    
    async with FastmcpClient("test_client", config, max_retries=3) as client:

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

        query1 = "阿里巴巴怎么样？"
        query2 = "分析下寒武纪"
        query3 = "分析一下纽威股份"

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

            # ("extract_entities_code", {"query": query2}),
            # ("extract_entities_code", {"query": query3}),

            # ("bailian_web_search", {"query": "阿里巴巴怎么样？"}),
            # ("bailian_web_parser", {"url": "https://xueqiu.com/1821992043/355703692"}),
            # ("crawl_ths_company", {"query": query2, "code": "688256"}),
            # ("crawl_ths_holder", {"query": query2, "code": "688256"}),
            # ("crawl_ths_operate", {"query": query2, "code": "688256"}),
            # ("crawl_ths_equity", {"query": query2, "code": "688256"}),
            # ("crawl_ths_capital", {"query": query2, "code": "688256"}),
            # ("crawl_ths_worth", {"query": query2, "code": "688256"}),
            # ("crawl_ths_news", {"query": query2, "code": "688256"}),
            # ("crawl_ths_concept", {"query": query2, "code": "688256"}),
            # ("crawl_ths_position", {"query": query2, "code": "688256"}),
            # ("crawl_ths_finance", {"query": query2, "code": "688256"}),
            # ("crawl_ths_bonus", {"query": query2, "code": "688256"}),
            # ("crawl_ths_event", {"query": query2, "code": "688256"}),
            # ("crawl_ths_field", {"query": query2, "code": "688256"}),

            # ("crawl_ths_company", {"query": query3, "code": "603699"}),
            # ("crawl_ths_bonus", {"query": query3, "code": "603699"}),
            ("crawl_ths_operate", {"query": query3, "code": "603699"}),
            # ("extract_query", {"query": "巴巴和小米怎么样"}),
            # ("company_factor", {"name": "紫金矿业", "code": "601899"}),
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
