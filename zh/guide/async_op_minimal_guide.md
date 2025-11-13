## 编写异步 Op 最简示例

这是一个最简单的异步 Op 示例，展示核心功能：注册、读取输入、写输出、如何跑Op测试。

---

### 完整示例

```python
from flowllm.core.context import C
from flowllm.core.op.base_async_op import BaseAsyncOp
from flowllm.main import FlowLLMApp
import asyncio

@C.register_op()
class SimpleChatOp(BaseAsyncOp):
    async def async_execute(self):
        # 1. 读取输入
        query = self.context.get("query", "")

        # 2. 处理逻辑（这里只是简单示例）
        result = f"你问的是：{query}"

        # 3. 写输出到 context（供其他 Op 使用）
        self.context["result"] = result

        # 4. 写输出到 context.response（整个 pipeline 的最终输出）
        self.context.response.answer = result

# 使用
async def main():
    async with FlowLLMApp() as app:
        result = await SimpleChatOp().async_call(query="你好？")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 要点说明

1. **注册 Op**：使用 `@C.register_op()` 装饰器
2. **读取输入**：`query = self.context.get("query", "")`
3. **写输出到 context**：`self.context["result"] = result`（供其他 Op 使用）
4. **写输出到 response**：`self.context.response.answer = result`（整个 pipeline 的最终输出）
5. **使用**：需要在 `FlowLLMApp()` 上下文里调用
