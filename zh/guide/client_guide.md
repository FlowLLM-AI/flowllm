### FlowLLM Client 使用指南

本指南介绍三种客户端调用模式：
- **HTTP**：同步返回结果
- **HTTP-Stream**：流式返回片段
- **MCP**：基于 SSE 的 Model Context Protocol 客户端交互


## 快速开始

**前置条件**：确保服务端已启动
- HTTP/HTTP-Stream 服务：默认端口 8002
- MCP SSE 服务：默认端口 8001，路径 `/sse`

**核心类**：
- `flowllm.core.utils.HttpClient`
- `flowllm.core.utils.FastMcpClient`


## 完整示例

示例包含三种模式的调用：
- HTTP 同步调用 Flow
- HTTP-Stream 流式调用 Flow
- MCP 工具枚举与调用

```python
import asyncio
import json

from flowllm.core.utils import HttpClient, FastMcpClient


async def run_http_examples():
    async with HttpClient("http://0.0.0.0:8002") as client:
        # 健康检查
        health = await client.health_check()
        print("health:", json.dumps(health, indent=2, ensure_ascii=False))

        # 列出可用 endpoints
        schema = await client.list_endpoints()
        print("endpoints keys:", list(schema.get("paths", {}).keys()))

        # 同步执行 Flow
        resp = await client.execute_flow("demo_http_flow", query="阿里巴巴前景如何？")
        print("sync answer:", getattr(resp, "answer", None))

        # 流式执行 Flow
        async for chunk in client.execute_stream_flow("demo_stream_http_flow", query="what is ai"):
            print(f"[{chunk.get('type','answer')}] {chunk.get('content','')}")


async def run_mcp_example():
    config = {
        "type": "sse",
        "url": "http://0.0.0.0:8001/sse",
        "headers": {},
        "timeout": 30.0,
    }
    async with FastMcpClient("test_client", config, max_retries=3) as client:
        tool_calls = await client.list_tool_calls()
        if tool_calls:
            for tool_call in tool_calls:
                # 模型需要的tool call格式（qwen）
                print(tool_call.simple_input_dump())

        # 调用工具
        result = await client.call_tool("demo_mcp_flow", {"query": "阿里巴巴前景怎么样？"})
        if result.is_error:
            print("MCP tool error:", result.content[0].text if result.content else "Unknown")
        else:
            print("MCP tool ok:", result.content[0].text if result.content else None)
            if result.structured_content:
                print(json.dumps(result.structured_content, indent=2, ensure_ascii=False))


async def main():
    await run_http_examples()
    await run_mcp_example()


if __name__ == "__main__":
    asyncio.run(main())
```


## HTTP 模式

- **初始化**：`HttpClient(base_url)` 使用上下文管理器管理会话
- **健康检查**：`health_check()` 返回服务端状态字典
- **列出接口**：`list_endpoints()` 返回 OpenAPI schema，通过 `schema.get("paths", {})` 获取路径列表
- **执行 Flow**：`execute_flow(flow_name, **kwargs)` 第一个参数为 Flow 名称，关键字参数作为请求体，返回响应对象（通常包含 `answer` 属性）


## HTTP-Stream 模式

- **流式执行**：`execute_stream_flow(flow_name, **kwargs)` 返回异步迭代器
- **消费片段**：使用 `async for chunk in ...` 迭代，每个 `chunk` 包含 `type` 和 `content` 字段
- **片段类型**：`type` 标识片段类型（如 "answer"），`content` 为实际内容


## MCP 模式

MCP 通过 SSE 提供工具列表与工具调用的抽象。

- **初始化**：`FastMcpClient(client_name, config, max_retries)` 配置包含：
  - `type`: "sse"
  - `url`: SSE 服务地址
  - `headers`: 可选请求头
  - `timeout`: 超时时间（秒）

- **列出工具**：`list_tool_calls()` 返回工具签名列表，每个工具对象包含名称、参数等信息

- **调用工具**：`call_tool(tool_name, arguments)` 返回 `CallToolResult`：
  - `content`: 消息内容列表，通过 `result.content[0].text` 访问
  - `structured_content`: 结构化返回（dict/list）
  - `is_error`: 是否出错（bool）


## 运行与调试

运行测试脚本（需先启动服务端）：

```bash
python -m flowllm.tests.http_client_test
python -m flowllm.tests.mcp_client_test
```

**常见问题**：
- 确认服务端地址与端口与客户端配置一致
- 容器/代理环境需检查 CORS 和 SSE 设置
- 根据网络和模型响应速度调整 `timeout`


## 模式选择

- **HTTP**：短响应、一次性获取结果、执行时间可控
- **HTTP-Stream**：长响应、需要实时展示、改善交互体验
- **MCP**：工具调用与编排、需要工具列表与结构化结果


