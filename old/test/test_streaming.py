import time
import requests
import json
import sseclient

from flowllm.context.service_context import C
from flowllm.flow.gallery.streaming_mock_flow import StreamingMockFlow
from flowllm.service.base_service import BaseService
from flowllm.service.http_service import HttpService


def test_streaming_response():
    """Test streaming response from HTTP service"""
    # Register streaming mock tool flow
    mock_flow = StreamingMockFlow()
    C.register_flow("streaming_mock")(mock_flow)
    
    # Start HTTP service in a separate thread
    import threading
    service = BaseService.get_service("config=default")
    thread = threading.Thread(target=service, daemon=True)
    thread.start()
    
    # Wait for service to start
    time.sleep(2)
    
    # Test regular endpoint
    response = requests.post("http://localhost:8000/streaming_mock", json={"input_data": "test data"})
    print(f"Regular response: {response.json()}")
    
    # Test streaming endpoint
    url = "http://localhost:8000/streaming_mock/stream"
    headers = {"Accept": "text/event-stream"}
    response = requests.post(url, json={"input_data": "test data"}, headers=headers, stream=True)
    
    client = sseclient.SSEClient(response)
    for event in client.events():
        if event.data:
            try:
                data = json.loads(event.data)
                print(f"Streaming chunk: {data}")
                if data.get("is_complete"):
                    break
            except json.JSONDecodeError:
                print(f"Non-JSON data: {event.data}")


if __name__ == "__main__":
    test_streaming_response()
