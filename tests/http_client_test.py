"""Test module for HttpClient functionality.

This module contains tests and examples demonstrating the usage of HttpClient
for interacting with flow execution endpoints, including health checks,
endpoint listing, synchronous flow execution, and streaming flow execution.
"""

import asyncio
import json

from flowllm.core.utils import HttpClient


async def main():
    """Test function for HttpClient.

    This function demonstrates how to use HttpClient to:
    - Check health status
    - List available endpoints
    - Execute flows synchronously
    - Execute flows with streaming
    """
    async with HttpClient("http://0.0.0.0:8002") as client:

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
            openapi_schema = await client.list_endpoints()
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

        query = "阿里巴巴前景如何？"

        response = await client.execute_flow("demo_http_flow", query=query)
        print(f"result: {response.answer}")

        # Example curl command for streaming endpoint:
        # curl -X POST http://localhost:8002/demo_stream_http_flow \
        #   -H "Content-Type: application/json" \
        #   -d '{
        #     "query": "what is ai"
        #   }'
        print("=" * 50)
        print("Testing streaming endpoint...")
        try:
            async for chunk in client.execute_stream_flow(
                "demo_stream_http_flow",
                query="what is ai",
            ):
                chunk_type = chunk.get("type", "answer")
                chunk_content = chunk.get("content", "")
                if chunk_content:
                    print(f"[{chunk_type}] {chunk_content}")
        except Exception as e:
            print(f"Streaming test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
