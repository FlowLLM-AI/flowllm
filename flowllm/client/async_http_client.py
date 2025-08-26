from typing import Dict

import httpx

from flowllm.schema.flow_response import FlowResponse


class AsyncHttpClient:
    """Async client for interacting with FlowLLM HTTP service"""

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 3600.0):
        """
        Initialize async HTTP client

        Args:
            base_url: Base URL of the FlowLLM HTTP service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')  # Remove trailing slash for consistent URL formatting
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)  # Create async HTTP client with timeout

    async def __aenter__(self):
        """Async context manager entry - returns self for 'async with' usage"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures proper cleanup of HTTP client"""
        await self.client.aclose()

    async def close(self):
        """Explicitly close the HTTP client connection"""
        await self.client.aclose()

    async def health_check(self) -> Dict[str, str]:
        """
        Perform health check on the FlowLLM service
        
        Returns:
            Dict containing health status information from the service
            
        Raises:
            httpx.HTTPStatusError: If the service is not healthy or unreachable
        """
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()  # Raise exception for HTTP error status codes
        return response.json()

    async def execute_tool_flow(self, flow_name: str, **kwargs) -> FlowResponse:
        """
        Execute a specific tool flow on the FlowLLM service
        
        Args:
            flow_name: Name of the tool flow to execute
            **kwargs: Additional parameters to pass to the tool flow
            
        Returns:
            FlowResponse object containing the execution results
            
        Raises:
            httpx.HTTPStatusError: If the request fails or flow execution errors
        """
        endpoint = f"{self.base_url}/{flow_name}"
        response = await self.client.post(endpoint, json=kwargs)  # Send flow parameters as JSON
        response.raise_for_status()  # Raise exception for HTTP error status codes
        result_data = response.json()
        return FlowResponse(**result_data)  # Parse response into FlowResponse schema

    async def list_tool_flows(self) -> list:
        """
        Get list of available tool flows from the FlowLLM service
        
        Returns:
            List of available tool flow names and their metadata
            
        Raises:
            httpx.HTTPStatusError: If the service is unreachable or returns an error
        """
        response = await self.client.get(f"{self.base_url}/list")
        response.raise_for_status()  # Raise exception for HTTP error status codes
        return response.json()
