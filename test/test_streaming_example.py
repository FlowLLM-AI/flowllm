import time
import requests
import json
import sseclient
import threading

from flowllm.context.service_context import C
from flowllm.service.base_service import BaseService
from flowllm.flow.gallery.streaming_example_flow import StreamingExampleFlow


def test_streaming_example():
    """测试流式输出示例"""
    # 注册流式输出示例流程
    C.register_flow("streaming_example")(StreamingExampleFlow())
    
    # 在单独的线程中启动HTTP服务
    service = BaseService.get_service("config=default")
    thread = threading.Thread(target=service, daemon=True)
    thread.start()
    
    # 等待服务启动
    time.sleep(2)
    
    # 测试常规端点
    print("\n测试常规端点:")
    response = requests.post(
        "http://localhost:8000/streaming_example_flow", 
        json={"text": "这是一个流式输出的测试示例，看看效果如何。"}
    )
    print(f"常规响应: {response.json()}")
    
    # 测试流式端点
    print("\n测试流式端点:")
    url = "http://localhost:8000/streaming_example_flow/stream"
    headers = {"Accept": "text/event-stream"}
    response = requests.post(
        url, 
        json={"text": "这是一个流式输出的测试示例，看看效果如何。", "delay": 0.3}, 
        headers=headers, 
        stream=True
    )
    
    client = sseclient.SSEClient(response)
    for event in client.events():
        if event.data:
            if event.data == "[DONE]":
                print("\n流式输出完成")
                break
                
            try:
                data = json.loads(event.data)
                chunk_type = data.get("chunk_type", "")
                chunk = data.get("chunk", "")
                
                if chunk_type == "think":
                    print(f"\n[思考] {chunk}")
                elif chunk_type == "answer":
                    print(chunk, end="", flush=True)
                else:
                    print(f"\n[{chunk_type}] {chunk}")
                    
                if data.get("done"):
                    print("\n流式输出完成")
                    break
            except json.JSONDecodeError:
                print(f"\n非JSON数据: {event.data}")


if __name__ == "__main__":
    test_streaming_example()
