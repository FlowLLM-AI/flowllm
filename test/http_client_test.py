import asyncio
import json

from flowllm.client import AsyncHttpClient


async def main():
    async with AsyncHttpClient("http://0.0.0.0:8001") as client:

        # Test 1: Health check
        print("=" * 50)
        print("Testing health check endpoint...")
        try:
            health_result = await client.health_check()
            print(f"Health check result: {json.dumps(health_result, indent=2)}")
        except Exception as e:
            print(f"Health check failed: {e}")

        # Test 2: Get available endpoints
        print("=" * 50)
        print("Getting available endpoints...")
        try:
            openapi_schema = await client.list_available_endpoints()
            if openapi_schema and "paths" in openapi_schema:
                print("Available endpoints:")
                for path, methods in openapi_schema["paths"].items():
                    for method, details in methods.items():
                        if method.upper() == "POST":
                            print(f"  {method.upper()} {path} - {details.get('summary', 'No description')}")
            else:
                print("Could not retrieve endpoint information")
        except Exception as e:
            print(f"Failed to get endpoints: {e}")

        query1 = "阿里巴巴怎么样？"
        query2 = "寒武纪还可以买吗？"

        # response = await client.execute_flow("mock_tool_flow", a=query2)
        # print(f"result: {response.answer}")
        #
        # response = await client.execute_flow("mock_async_tool_flow", a=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("ant_search", query="阿里巴巴怎么样？", entity="阿里巴巴")
        # print(f"result: {response.answer}")
        #
        # response = await client.execute_flow("ant_investment", entity="阿里巴巴", analysis_category="股票")
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("dashscope_search_tool_flow", query="阿里巴巴怎么样？")
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("get_a_stock_infos", query=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("get_a_stock_news", query=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("llm_flow", query=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("react_llm_tool_flow", query=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("tavily_search_tool_flow", query=query2)
        # print(f"result: {response.answer}")

        """
        curl -X POST http://0.0.0.0:8001/llm_flow_stream -H "Content-Type: application/json" -d '{"query": "what is AI?"}'
        """


if __name__ == "__main__":
    asyncio.run(main())
