## HTTP 流式服务快速上手

本指南演示如何在 FlowLLM 中搭建一个支持流式响应的 HTTP 服务，覆盖：编写流式 Op、配置流式 Flow、启动服务与客户端流式调用。

---

### 一、编写流式 Op

流式 Op 与普通 Op 的主要区别在于使用 `self.context.add_stream_chunk()` 来发送流式数据块，而不是一次性返回完整结果。基类见 `flowllm/core/op/base_async_op.py`：

```python
from ..core.context import C
from ..core.op import BaseAsyncOp
from ..core.enumeration import ChunkEnum, Role
from ..core.schema import FlowStreamChunk, Message

@C.register_op()
class StreamChatOp(BaseAsyncOp):
    file_path: str = __file__

    async def async_execute(self):
        messages = self.context.messages
        system_prompt = self.context.system_prompt

        # 构建包含系统提示的消息列表
        messages = [Message(role=Role.SYSTEM, content=system_prompt)] + messages

        # 从 LLM 获取流式响应
        async for stream_chunk in self.llm.astream_chat(messages):
            assert isinstance(stream_chunk, FlowStreamChunk)
            # 只处理特定类型的块（答案、思考、错误、工具调用）
            if stream_chunk.chunk_type in [
                ChunkEnum.ANSWER,
                ChunkEnum.THINK,
                ChunkEnum.ERROR,
                ChunkEnum.TOOL
            ]:
                # 将流式块添加到上下文，会自动发送到客户端
                await self.context.add_stream_chunk(stream_chunk)
```

要点：
- 类名需以 `Op` 结尾（框架有断言）
- 用 `@C.register_op()` 注册后方可在 Flow 中引用
- 流式 Op 继承 `BaseAsyncOp` 并实现 `async_execute`
- 使用 `self.context.add_stream_chunk(stream_chunk)` 发送流式数据块
- 流式块类型包括：`ANSWER`（答案）、`THINK`（思考过程）、`ERROR`（错误）、`TOOL`（工具调用）
- 框架会自动处理流式传输，无需手动管理连接

---

### 二、编写 yaml config

保存如下配置为：
- 覆盖默认：`flowllm/flowllm/config/default.yaml`
- 自定义：项目根新建 `my_stream_config.yaml`

```yaml
backend: http
thread_pool_max_workers: 128

http:
  host: "0.0.0.0"
  port: 8002

flow:
  # 流式 HTTP 流程（POST /demo_stream_http_flow）
  demo_stream_http_flow:
    flow_content: GenSystemPromptOp() >> StreamChatOp()
    stream: true  # 关键：标识这是一个流式 Flow
    description: "AI 对话助手（流式返回）"
    input_schema:
      query:
        type: string
        description: "用户问题"
        required: true

llm:
  default:
    backend: openai_compatible
    model_name: qwen3-30b-a3b-instruct-2507
    params:
      temperature: 0.6

embedding_model:
  default:
    backend: openai_compatible
    model_name: text-embedding-v4
    params:
      dimensions: 1024

vector_store:
  default:
    backend: memory
    embedding_model: default
```

要点：
- **关键配置**：在 Flow 配置中添加 `stream: true` 标识，框架会自动将其注册为流式端点
- Flow 的编排在 `flow_content` 中定义，流式 Op（如 `StreamChatOp`）可以与其他 Op 组合
- `backend: http` 指定以 HTTP 服务启动
- `input_schema` 在 HTTP 模式下可选，建议填写以生成更完善的 OpenAPI 与入参校验
- `llm/embedding_model/vector_store` 为默认能力，可按需替换
- 更多 Flow 表达式与字段说明，参考：
  - `docs/zh/guide/flow_guide.md`
  - `docs/zh/guide/config_guide.md`

---

### 三、启动服务

确保已安装 FlowLLM，并在`.env`中设置模型相关环境变量，可直接参考项目根的示例文件 `example.env`：
```bash
export FLOW_LLM_API_KEY="sk-xxxx"
export FLOW_LLM_BASE_URL="https://xxxx/v1"
export FLOW_EMBEDDING_API_KEY="sk-xxxx"
export FLOW_EMBEDDING_BASE_URL="https://xxxx/v1"
```

- 使用my_stream_config启动：
```bash
flowllm config=my_stream_config backend=http
```

成功后：
- 健康检查：`GET http://0.0.0.0:8002/health`
- OpenAPI：`GET http://0.0.0.0:8002/docs`
- 流式接口：`POST http://0.0.0.0:8002/demo_stream_http_flow`

服务行为（见 `flowllm/core/service/http_service.py`）：
- 为每个标记了 `stream: true` 的 Flow 生成流式 `POST /{flow_name}` 接口
- 使用 Server-Sent Events (SSE) 格式返回流式数据
- 自动注入 CORS（默认允许所有来源）
- 流式数据格式：每行以 `data:` 开头，包含 JSON 格式的 `FlowStreamChunk`，结束时发送 `data:[DONE]`

若使用 `demo_stream_http_flow`：`POST http://0.0.0.0:8002/demo_stream_http_flow`

---

### 四、客户端调用与测试

使用内置 `HttpClient` 进行流式调用：

```python
import asyncio
import json
from flowllm.core.utils import HttpClient


async def main():
    async with HttpClient("http://0.0.0.0:8002") as client:
        # 健康检查
        health = await client.health_check()
        print("health:", json.dumps(health, indent=2, ensure_ascii=False))

        # 查看可用 endpoints
        schema = await client.list_endpoints()
        print("endpoints:", list(schema.get("paths", {}).keys()))

        # 流式调用
        print("=" * 50)
        print("流式响应：")
        async for chunk in client.execute_stream_flow(
            "demo_stream_http_flow",
            query="什么是人工智能？"
        ):
            chunk_type = chunk.get("type", "answer")
            chunk_content = chunk.get("content", "")
            if chunk_content:
                # 根据块类型进行不同处理
                if chunk_type == "answer":
                    print(chunk_content, end="", flush=True)  # 实时打印答案
                elif chunk_type == "think":
                    # 思考过程可以单独处理
                    print(f"\n[思考] {chunk_content}", end="", flush=True)
                elif chunk_type == "tool":
                    print(f"\n[工具调用] {chunk_content}")
                elif chunk_type == "error":
                    print(f"\n[错误] {chunk_content}")
        print("\n" + "=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
```

也可直接运行内置测试脚本（以 `demo_stream_http_flow` 为例）：

```bash
python -m flowllm.tests.http_client_test
```

**流式响应格式说明**：
- 每个 chunk 是一个字典，包含：
  - `type`: 块类型（`answer`、`think`、`tool`、`error`）
  - `content`: 块内容（字符串或 JSON）
- 流式响应使用 SSE 格式，客户端通过 `async for` 循环接收
- 当收到 `[DONE]` 信号时，流式传输结束

**使用 curl 测试流式接口**：

```bash
curl -X POST http://localhost:8002/demo_stream_http_flow \
  -H "Content-Type: application/json" \
  -d '{
    "query": "what is ai"
  }'
```

---

### 五、流式 vs 同步接口对比

| 特性 | 同步接口 | 流式接口 |
|------|---------|---------|
| 配置 | 无需特殊配置 | 需设置 `stream: true` |
| Op 实现 | 使用 `self.context.response.answer` | 使用 `self.context.add_stream_chunk()` |
| 返回方式 | 一次性返回完整结果 | 实时返回数据块 |
| 适用场景 | 快速响应、简单查询 | 长文本生成、实时反馈、思考过程展示 |
| 客户端调用 | `execute_flow()` | `execute_stream_flow()` |
| 响应格式 | JSON | SSE (Server-Sent Events) |
