import asyncio
import json
from typing import Dict, Any

import httpx
from loguru import logger

from flowllm.schema.flow_response import FlowResponse


class HttpClientTest:
    def __init__(self, base_url: str = "http://0.0.0.0:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

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

        # Test 3: Test default flow
        print("=" * 50)
        print("Testing default flow...")
        try:
            flow_result = await client.execute_flow("default", a="test_value_a", b="test_value_b")
            print(f"Flow execution result:")
            print(f"  Success: {flow_result.success}")
            print(f"  Answer: {flow_result.answer}")
            print(f"  Messages count: {len(flow_result.messages)}")
            print(f"  Metadata: {json.dumps(flow_result.metadata, indent=2)}")
        except Exception as e:
            print(f"Default flow execution failed: {e}")

        # Test 4: Test mock_flow
        print("=" * 50)
        print("Testing mock_flow...")
        try:
            mock_flow_result = await client.execute_flow("mock_flow", a="mock_a", b="mock_b")
            print(f"Mock flow execution result:")
            print(f"  Success: {mock_flow_result.success}")
            print(f"  Answer: {mock_flow_result.answer}")
            print(f"  Messages count: {len(mock_flow_result.messages)}")
            print(f"  Metadata: {json.dumps(mock_flow_result.metadata, indent=2)}")
        except Exception as e:
            print(f"Mock flow execution failed: {e}")

        # Test 5: Test flow with optional parameters
        print("=" * 50)
        print("Testing flow with minimal required parameters...")
        try:
            minimal_result = await client.execute_flow("default", a="minimal_a", b="minimal_b")
            print(f"Minimal parameters result:")
            print(f"  Success: {minimal_result.success}")
            print(f"  Answer: {minimal_result.answer}")
        except Exception as e:
            print(f"Minimal parameters test failed: {e}")

        # Test 6: Test error handling - invalid flow
        print("=" * 50)
        print("Testing error handling with invalid flow...")
        try:
            error_result = await client.execute_flow("nonexistent_flow", a="test", b="test")
            print(f"Unexpected success with invalid flow: {error_result}")
        except httpx.HTTPStatusError as e:
            print(f"Expected error for invalid flow: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Error handling test result: {e}")

        # Test 7: Test missing required parameters
        print("=" * 50)
        print("Testing missing required parameters...")
        try:
            missing_params_result = await client.execute_flow("default", a="only_a")  # missing 'b'
            print(f"Unexpected success with missing params: {missing_params_result}")
        except httpx.HTTPStatusError as e:
            print(f"Expected validation error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"Missing parameters test result: {e}")


if __name__ == "__main__":
    print("FlowLLM HTTP Client Test")
    print("Make sure the HTTP service is running on http://0.0.0.0:8001")
    print("You can start it with: python -m flowllm.app --backend http")
    print()

    asyncio.run(main())
