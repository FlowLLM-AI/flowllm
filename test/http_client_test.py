import asyncio
import json
from typing import Dict, Any

import httpx
from loguru import logger

from flowllm.schema.flow_response import FlowResponse


class HttpClientTest:
    def __init__(self, base_url: str = "http://0.0.0.0:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30000.0)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def health_check(self) -> Dict[str, Any]:
        """Test the health check endpoint"""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def execute_flow(self, flow_name: str, **kwargs) -> FlowResponse:
        """Execute a flow endpoint"""
        endpoint = f"{self.base_url}/{flow_name}"
        response = await self.client.post(endpoint, json=kwargs)
        response.raise_for_status()
        return FlowResponse(**response.json())

    async def list_available_endpoints(self) -> Dict[str, Any]:
        """Get OpenAPI schema to see available endpoints"""
        try:
            response = await self.client.get(f"{self.base_url}/openapi.json")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.warning(f"Could not fetch OpenAPI schema: {e}")
            return {}


async def main():
    async with HttpClientTest("http://0.0.0.0:8001") as client:

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

        # response = await client.execute_flow("ant_search", query="阿里巴巴怎么样？", entity="阿里巴巴")
        # print(f"result: {response.answer}")

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

        # response = await client.execute_flow("mock_tool_flow", a=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("mock_async_tool_flow", a=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("react_llm_tool_flow", query=query2)
        # print(f"result: {response.answer}")

        # response = await client.execute_flow("simple_llm_tool_flow", query=query2)
        # print(f"result: {response.answer}")

        response = await client.execute_flow("tavily_search_tool_flow", query=query2)
        print(f"result: {response.answer}")

        """
        curl -X POST http://0.0.0.0:8001/llm_flow_stream -H "Content-Type: application/json" -d '{"query": "what is AI?"}'
        """


if __name__ == "__main__":
    print("FlowLLM HTTP Client Test")
    print("Make sure the HTTP service is running on http://0.0.0.0:8001")
    print("You can start it with: python -m flowllm.app --backend http")
    print()

    asyncio.run(main())
