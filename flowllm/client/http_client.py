from typing import Dict, Any, Optional

import httpx

from flowllm.schema.flow_response import FlowResponse


class HttpClient:
    """Client for interacting with FlowLLM HTTP service"""

    def __init__(self, base_url: str = "http://localhost:8001", timeout: float = 600.0):
        """
        Initialize HTTP client
        
        Args:
            base_url: Base URL of the FlowLLM HTTP service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

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

    def get_available_flows(self) -> Optional[Dict[str, Any]]:
        # TODO add available_flows
        response = self.client.get(f"{self.base_url}/flows")
        response.raise_for_status()
        return response.json()
