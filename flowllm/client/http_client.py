from typing import Dict

import httpx

from flowllm.schema.flow_response import FlowResponse


class HttpClient:

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 3600):
        self.base_url = base_url.rstrip('/')  # Remove trailing slash for consistent URL formatting
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)  # Create synchronous HTTP client with timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def close(self):
        self.client.close()

    def health_check(self) -> Dict[str, str]:
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def execute_flow(self, flow_name: str, **kwargs) -> FlowResponse:
        endpoint = f"{self.base_url}/{flow_name}"
        response = self.client.post(endpoint, json=kwargs)
        response.raise_for_status()
        result_data = response.json()
        return FlowResponse(**result_data)
