import asyncio
import json

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

        test_cases = [
            # ("ant_search", {"query": query1, "entity": "阿里巴巴"}),
            # ("ant_investment", {"entity": "阿里巴巴", "analysis_category": "股票"}),

            # ("tavily_search", {"query": query1}),
            # ("dashscope_search", {"query": query1}),
            # ("brave_web_search", {"query": query1}),
            # ("bailian_web_search", {"query": query1}),
            # ("bocha_web_search", {"query": query1}),
            # ("bailian_web_parser", {"url": "https://basic.10jqka.com.cn/601899/field.html"}),
            # ("bailian_web_parser", {"url": "https://basic.10jqka.com.cn/601899/company.html"}),

            # ("extract_entities_code", {"query": "阿里和腾讯哪个更好？和茅台比呢？"}),
            # ("akshare_market", {"code": "000001"}),
            # ("akshare_calculate", {"query": "平安银行最近行情走势", "code": "000001"}),

            # THS公司各类信息爬取测试
            # ("crawl_ths_company", {"query": "平安银行的公司情况如何？", "code": "000001"}),
            # ("crawl_ths_holder", {"query": "平安银行的股东结构如何？", "code": "000001"}),
            # ("crawl_ths_operate", {"query": "平安银行的主营业务是什么？", "code": "000001"}),
            # ("crawl_ths_equity", {"query": "平安银行的股本结构如何？", "code": "000001"}),
            # ("crawl_ths_capital", {"query": "平安银行有哪些资本运作？", "code": "000001"}),
            # ("crawl_ths_worth", {"query": "平安银行的业绩预测如何？", "code": "000001"}),
            # ("crawl_ths_news", {"query": "平安银行最近有什么新闻？", "code": "000001"}),
            # ("crawl_ths_concept", {"query": "平安银行涉及哪些概念题材？", "code": "000001"}),
            # ("crawl_ths_position", {"query": "平安银行的机构持仓情况如何？", "code": "000001"}),
            # ("crawl_ths_finance", {"query": "平安银行的财务状况如何？", "code": "000001"}),
            # ("crawl_ths_bonus", {"query": "平安银行的分红情况如何？", "code": "000001"}),
            # ("crawl_ths_event", {"query": "平安银行最近有什么重大事件？", "code": "000001"}),
            # ("crawl_ths_field", {"query": "平安银行在行业中的地位如何？", "code": "000001"}),
            
            # 测试其他股票代码
            # ("crawl_ths_company", {"query": "紫金矿业的公司情况如何？", "code": "601899"}),
            # ("crawl_ths_finance", {"query": "紫金矿业的财务指标怎么样？", "code": "601899"}),

        ]

        for tool_name, arguments in test_cases:
            print("=" * 100)
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
    asyncio.run(main())
