from typing import Dict

import httpx

from flowllm.schema.flow_response import FlowResponse


class AsyncHttpClient:

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 3600):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def close(self):
        await self.client.aclose()

    async def health_check(self) -> Dict[str, str]:
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    async def execute_flow(self, flow_name: str, **kwargs) -> FlowResponse:
        endpoint = f"{self.base_url}/{flow_name}"
        response = await self.client.post(endpoint, json=kwargs)
        response.raise_for_status()
        return FlowResponse(**response.json())

    async def list_available_endpoints(self) -> dict:
        response = await self.client.get(f"{self.base_url}/openapi.json")
        response.raise_for_status()
        return response.json()
