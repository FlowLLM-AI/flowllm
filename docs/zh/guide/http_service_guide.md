## HTTP 服务快速上手

本指南演示如何在 FlowLLM 中以最小工作量搭建一个可调用的 HTTP 服务，覆盖：编写 Op、编排 Flow、配置、启动与客户端调用。

---

### 一、编写 Op

HTTP 工具的业务逻辑来源于 Flow 中的 Op。基类见 `flowllm/core/op/base_op.py`，异步基类为 `BaseAsyncOp`：

```python
from flowllm.core.context import C
from flowllm.core.op import BaseAsyncOp

@C.register_op()
class EchoOp(BaseAsyncOp):
    async def async_execute(self):
        text = self.context.get("text", "")
        self.context.response.answer = f"echo: {text}"
```

要点：
- 类名需以 `Op` 结尾（框架有断言）
- 用 `@C.register_op()` 注册后方可在 Flow 中引用
- 对话型 Op 通常继承 `BaseAsyncOp` 并实现 `async_execute`
- 可通过 `self.context` 读写上下文，`self.llm` 调用模型，`self.prompt_format()` 绑定同名 `*_prompt.yaml`
- 单元：以最小上下文执行 `EchoOp.async_execute`，断言 `context.response.answer`
- 端到端：启动 HTTP 服务后用客户端调用并断言（见“客户端调用与测试”）

---

### 二、编写yaml config

保存如下配置为：
- 覆盖默认：`flowllm/flowllm/config/default.yaml`
- 自定义：项目根新建 `my_http_config.yaml`

```yaml
backend: http
thread_pool_max_workers: 128

http:
  host: "0.0.0.0"
  port: 8002

flow:
  demo_http_flow:
    flow_content: GenSystemPromptOp() >> ChatOp()
    description: "AI assistant"
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
- Flow 的编排直接在配置文件的 `flow` 段中定义（如上 `demo_http_flow`）。若要将自定义的 `EchoOp` 暴露为接口，可将其填入对应 `flow_content`；通用对话可参考 `GenSystemPromptOp() >> ChatOp()`。
- `backend: http` 指定以 HTTP 服务启动
- `flow` 定义同步接口
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

- 使用my_http_config启动：
```bash
flowllm config=my_http_config backend=http
```

成功后：
- 健康检查：`GET http://0.0.0.0:8002/health`
- OpenAPI：`GET http://0.0.0.0:8002/docs`
- 同步接口：`POST http://0.0.0.0:8002/demo_http_flow`

服务行为（见 `flowllm/core/service/http_service.py`）：
- 为每个 Flow 生成 `POST /{flow_name}` 接口
- 自动注入 CORS（默认允许所有来源）

若使用 `demo_http_flow`：`POST http://0.0.0.0:8002/demo_http_flow`

---

### 四、客户端调用与测试

使用内置 `HttpClient` 进行调用：

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

        # 同步调用
        resp = await client.execute_flow("demo_http_flow", query="阿里巴巴前景如何？")
        print("sync answer:", getattr(resp, "answer", None))


if __name__ == "__main__":
    asyncio.run(main())
```

也可直接运行内置测试脚本（以 `demo_http_flow` 为例）：

```bash
python -m flowllm.tests.http_client_test
```
