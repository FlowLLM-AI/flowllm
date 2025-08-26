from typing import Dict

import httpx

from flowllm.schema.flow_response import FlowResponse


class HttpClient:
    """Client for interacting with FlowLLM HTTP service"""

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 3600.0):
        """
        Initialize HTTP client
        
        Args:
            base_url: Base URL of the FlowLLM HTTP service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')  # Remove trailing slash for consistent URL formatting
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)  # Create synchronous HTTP client with timeout

    def __enter__(self):
        """Context manager entry - returns self for 'with' usage"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures proper cleanup of HTTP client"""
        self.client.close()

    def close(self):
        """Explicitly close the HTTP client connection"""
        self.client.close()

    def health_check(self) -> Dict[str, str]:
        """
        Perform health check on the FlowLLM service
        
        Returns:
            Dict containing health status information from the service
            
        Raises:
            httpx.HTTPStatusError: If the service is not healthy or unreachable
        """
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()  # Raise exception for HTTP error status codes
        return response.json()

    def execute_tool_flow(self, flow_name: str, **kwargs) -> FlowResponse:
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
        response = self.client.post(endpoint, json=kwargs)  # Send flow parameters as JSON
        response.raise_for_status()  # Raise exception for HTTP error status codes
        result_data = response.json()
        return FlowResponse(**result_data)  # Parse response into FlowResponse schema

    def list_tool_flows(self) -> list:
        """
        Get list of available tool flows from the FlowLLM service
        
        Returns:
            List of available tool flow names and their metadata
            
        Raises:
            httpx.HTTPStatusError: If the service is unreachable or returns an error
        """
        response = self.client.get(f"{self.base_url}/list")
        response.raise_for_status()  # Raise exception for HTTP error status codes
        return response.json()
