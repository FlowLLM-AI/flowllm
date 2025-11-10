"""Asynchronous HTTP client for executing flows with retry mechanism.

This module provides an HttpClient class for making asynchronous HTTP requests
to flow endpoints with built-in retry logic and error handling.

Key features:
- Async/await support for non-blocking HTTP requests
- Automatic retry mechanism with configurable retry attempts
- Flexible error handling (raise exceptions or return None)
- Context manager support for resource cleanup
- Health check and endpoint listing capabilities
"""

import json
from typing import Dict, Optional, AsyncIterator

import httpx
from loguru import logger

from ..schema import FlowResponse


class HttpClient:
    """Asynchronous HTTP client for executing flows with retry mechanism.

    This class provides an async HTTP client for interacting with flow endpoints.
    It includes built-in retry logic, error handling, and context manager support.

    Features:
    - Automatic retry on failure with configurable retry attempts
    - Flexible error handling (raise exceptions or return None)
    - Async/await support for non-blocking operations
    - Context manager support for automatic resource cleanup
    - Health check and endpoint discovery capabilities
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        timeout: float = 3600,
        max_retries: int = 3,
        raise_exception: bool = True,
    ):
        """Initialize the async HTTP client.

        Args:
            base_url: Base URL for the flow service endpoint. Defaults to
                "http://localhost:8001".
            timeout: Request timeout in seconds. Defaults to 3600 (1 hour).
            max_retries: Maximum number of retry attempts on failure. Defaults to 3.
            raise_exception: Whether to raise exceptions on final failure. If False,
                returns None after all retries fail. Defaults to True.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.raise_exception = raise_exception
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        """Async context manager entry point.

        Returns:
            The HttpClient instance.
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit point.

        Closes the HTTP client connection and cleans up resources.

        Args:
            exc_type: Exception type if an exception occurred.
            exc_val: Exception value if an exception occurred.
            exc_tb: Exception traceback if an exception occurred.
        """
        await self.client.aclose()

    async def close(self):
        """Close the HTTP client connection and clean up resources.

        This method should be called when done using the client if not using
        the context manager (async with statement).
        """
        await self.client.aclose()

    async def health_check(self) -> Dict[str, str]:
        """Check the health status of the flow service.

        Makes a GET request to the /health endpoint to verify the service
        is running and responding.

        Returns:
            A dictionary containing health check information.

        Raises:
            httpx.HTTPStatusError: If the health check request fails.
        """
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def execute_flow(self, flow_name: str, **kwargs) -> Optional[FlowResponse]:
        """
        Execute the flow asynchronously with retry logic and error handling.

        This method:
        1. Makes HTTP POST request to the flow endpoint
        2. Retries on failure according to max_retries setting
        3. Returns FlowResponse or None based on raise_exception setting

        Args:
            flow_name: Name of the flow to execute
            **kwargs: Additional parameters passed to the flow

        Returns:
            FlowResponse on success, None on failure if raise_exception=False

        Raises:
            httpx.HTTPStatusError: If HTTP request fails and raise_exception=True

        curl example:
            curl -X POST http://localhost:8002/demo_http_flow \
              -H "Content-Type: application/json" \
              -d '{
                "query": "what is ai?"
              }'
        """
        endpoint = f"{self.base_url}/{flow_name}"
        result = None

        if self.max_retries == 1 and self.raise_exception:
            response = await self.client.post(endpoint, json=kwargs)
            response.raise_for_status()
            result = FlowResponse(**response.json())

        else:
            for i in range(self.max_retries):
                try:
                    response = await self.client.post(endpoint, json=kwargs)
                    response.raise_for_status()
                    result = FlowResponse(**response.json())
                    break
                except Exception as e:
                    logger.exception(
                        f"execute_flow failed for flow={flow_name}, attempt={i + 1}/{self.max_retries}, error={e.args}",
                    )

                    if i == self.max_retries - 1:
                        if self.raise_exception:
                            raise e

        return result

    async def list_endpoints(self) -> dict:
        """List all available endpoints from the flow service.

        Retrieves the OpenAPI specification which contains information about
        all available endpoints and their schemas.

        Returns:
            A dictionary containing the OpenAPI specification with endpoint
            information.

        Raises:
            httpx.HTTPStatusError: If the request to retrieve endpoints fails.
        """
        response = await self.client.get(f"{self.base_url}/openapi.json")
        response.raise_for_status()
        return response.json()

    async def execute_stream_flow(self, flow_name: str, **kwargs) -> AsyncIterator[Dict[str, str]]:
        """Execute the flow and stream responses as they arrive.

        This streams Server-Sent Events style lines from the endpoint, parsing
        entries that begin with "data:". Each valid JSON payload is expected to
        include keys like "chunk_type" and "chunk" and will be yielded as a
        dictionary: {"type": str, "content": str}. The stream terminates when a
        line with payload "[DONE]" is received.

        Args:
            flow_name: Name of the flow endpoint to call.
            **kwargs: JSON payload sent to the endpoint.

        Yields:
            Dict with keys "type" and "content" for each streamed chunk. If
            an error occurs and raise_exception=False, an error chunk will be yielded.
        """
        endpoint = f"{self.base_url}/{flow_name}"

        async with self.client.stream("POST", endpoint, json=kwargs) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("data:"):
                    data_content = line[5:].strip()

                    if data_content == "[DONE]":
                        break

                    try:
                        json_data = json.loads(data_content)
                        chunk_type = json_data.get("chunk_type", "answer")
                        chunk_content = json_data.get("chunk", "")

                        if chunk_content:
                            yield {"type": chunk_type, "content": chunk_content}
                    except Exception:
                        # Skip lines that aren't valid JSON payloads
                        continue
