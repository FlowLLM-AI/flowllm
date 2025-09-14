from typing import Dict

import httpx

from flowllm.schema.flow_response import FlowResponse


class AsyncHttpClient:

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 3600):
        self.base_url = base_url.rstrip('/')  # Remove trailing slash for consistent URL formatting
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)  # Create async HTTP client with timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def close(self):
        await self.client.aclose()

    async def health_check(self) -> Dict[str, str]:
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()  # Raise exception for HTTP error status codes
        return response.json()

    async def execute_flow(self, flow_name: str, **kwargs) -> FlowResponse:
        endpoint = f"{self.base_url}/{flow_name}"
        response = await self.client.post(endpoint, json=kwargs)  # Send flow parameters as JSON
        response.raise_for_status()  # Raise exception for HTTP error status codes
        result_data = response.json()
        return FlowResponse(**result_data)  # Parse response into FlowResponse schema
