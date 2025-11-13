## CMD 服务快速上手

本指南演示如何在 FlowLLM 中使用命令行模式执行单个 Op，覆盖：编写 Op 和直接运行命令。

---

### 一、编写 Op

CMD 工具的业务逻辑来源于 Flow 中的 Op。基类见 `flowllm/core/op/base_op.py`，异步基类为 `BaseAsyncOp`：

```python
from ..core.context import C
from ..core.op import BaseAsyncOp


@C.register_op()
class EchoOp(BaseAsyncOp):
    file_path: str = __file__

    async def async_execute(self):
        text = self.context.get("text", "")
        self.context.response.answer = f"echo: {text}"
```

要点：

- 类名需以 `Op` 结尾（框架有断言）
- 用 `@C.register_op()` 注册后方可在命令行中引用
- 对话型 Op 通常继承 `BaseAsyncOp` 并实现 `async_execute`
- 可通过 `self.context` 读写上下文，`self.llm` 调用模型，`self.prompt_format()` 绑定同名 `*_prompt.yaml`
- 参数通过 `self.context.get()` 获取

---

### 二、直接运行命令

确保已安装 FlowLLM，并在`.env`中设置模型相关环境变量，可直接参考项目根的示例文件 `example.env`：

```bash
export FLOW_LLM_API_KEY="sk-xxxx"
export FLOW_LLM_BASE_URL="https://xxxx/v1"
export FLOW_EMBEDDING_API_KEY="sk-xxxx"
export FLOW_EMBEDDING_BASE_URL="https://xxxx/v1"
```

运行示例：

```bash
flowllm backend=cmd cmd.flow="EchoOp()" cmd.params.text="Hello World"
```
