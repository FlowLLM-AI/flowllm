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
            # ("bailian_web_search", {"query": query1}),
            ("bocha_web_search", {"query": query1}),

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
    asyncio.run(main())
