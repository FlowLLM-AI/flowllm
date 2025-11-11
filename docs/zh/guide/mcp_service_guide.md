## MCP 服务快速上手

本指南演示如何在 FlowLLM 中以最小工作量搭建一个可调用的 MCP（Model Context Protocol）服务，覆盖：编写 Op、编排 Flow、配置、启动与客户端调用。

---

### 一、编写 Op

MCP 工具的业务逻辑来源于 Flow 中的 Op。可直接复用已有 Op，也可先编写一个简单示例。以下为内置示例 `MockSearchOp`：

```python
from ..core.context import C
from ..core.op import BaseAsyncOp
@C.register_op()
class MockSearchOp(BaseAsyncOp):
    """Mock search operation that uses LLM to generate realistic search results."""
    file_path: str = __file__

    async def async_execute(self):
        query = self.context.query
        if not query:
            self.context.response.answer = "No results found."
            return
        num_results = random.randint(0, 5)
        user_prompt = self.prompt_format("mock_search_op_prompt", query=query, num_results=num_results)
        messages = [
            Message(role=Role.SYSTEM, content="You are a helpful assistant that generates realistic search results in JSON format."),
            Message(role=Role.USER, content=user_prompt),
        ]
        def callback_fn(message: Message):
            return extract_content(message.content, "json")
        search_results: str = await self.llm.achat(messages=messages, callback_fn=callback_fn)
        self.context.response.answer = json.dumps(search_results, ensure_ascii=False, indent=2)
```

要点：
- 类名以 `Op` 结尾，且用 `@C.register_op()` 注册后方可在 Flow 中引用。
- 异步对话型 Op 继承 `BaseAsyncOp` 并实现 `async_execute`。
- 通过 `self.context` 读写上下文，`self.llm` 调用模型，`self.prompt_format()` 绑定提示词模板。

---

### 二、编排 Flow（示例）

将 `MockSearchOp` 编排为一个 Flow，供 MCP 工具调用：

```yaml
flow:
  demo_mcp_flow:
    flow_content: MockSearchOp()
    description: "search results for a given query."
    input_schema:
      query:
        type: string
        description: "user query"
        required: true
```

要点：
- Flow 名即工具名（如 `demo_mcp_flow`），在 MCP 中以同名工具暴露。
- `input_schema` 建议填写，便于客户端生成入参校验与帮助信息。

---

### 三、编写配置

保存如下配置为：
- 覆盖默认：`flowllm/flowllm/config/default.yaml`
- 自定义：项目根新建 `my_http_config.yaml`

```yaml
backend: mcp
thread_pool_max_workers: 128

mcp:
  transport: sse
  host: "0.0.0.0"
  port: 8001

flow:
  # 将 Flow 以 MCP 工具形式暴露（工具名：demo_mcp_flow）
  demo_mcp_flow:
    flow_content: MockSearchOp()
    description: "search results for a given query."
    input_schema:
      query:
        type: string
        description: "user query"
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
- `backend: mcp` 指定以 MCP 服务启动。
- `mcp.transport` 当前支持 `sse`；服务默认暴露 SSE 端点 `GET /sse`。
- `flow` 中声明的每个 Flow 都将作为一个 MCP 工具对外提供。

---

### 四、启动服务

确保已安装 FlowLLM，并在`.env`中设置模型相关环境变量，可直接参考项目根的示例文件 `example.env`：
```bash
export FLOW_LLM_API_KEY="sk-xxxx"
export FLOW_LLM_BASE_URL="https://xxxx/v1"
export FLOW_EMBEDDING_API_KEY="sk-xxxx"
export FLOW_EMBEDDING_BASE_URL="https://xxxx/v1"
```

- 使用默认配置（若默认配置仍为 `backend: http`，请显式覆盖为 MCP）：

```bash
flowllm config=my_http_config backend=mcp
```

- 使用自定义配置（推荐）：

```bash
flowllm config=my_mcp_config backend=mcp
```

成功后（以 `host=0.0.0.0`, `port=8001` 为例）：
- SSE 连接：`GET http://0.0.0.0:8001/sse`
- 工具清单与调用通过 SSE 渠道完成（由 MCP 客户端实现）

服务行为（参考 `flowllm/core/service/*` 内 MCP 相关实现）：
- 为每个 Flow 生成同名 MCP 工具（如 `demo_mcp_flow`）
- 采用 SSE 作为传输时，客户端通过单一 SSE 端点进行会话

---

### 五、客户端调用与测试

使用内置 `FastMcpClient` 进行调用（简化示例）：

```python
config = {
    "type": "sse",
    "url": "http://0.0.0.0:8001/sse",
    "headers": {},
    "timeout": 30.0,
}
async with FastMcpClient("test_client", config, max_retries=3) as client:
    # 1) 列出可用工具
    tool_calls = await client.list_tool_calls()
    # 2) 调用工具（与 Flow 同名）
    result = await client.call_tool("demo_mcp_flow", {"query": "阿里巴巴前景怎么样？"})
    # 3) 读取结果
    print(result)
```

也可直接运行内置测试脚本：

```bash
python -m flowllm.tests.mcp_client_test
```