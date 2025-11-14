## 编写异步 Op 快速入门（简单版）

这篇文档会告诉你如何快速写一个最简单的异步 Op，包含注册、读取输入、使用 LLM 和 prompt、写输出。

想看更复杂的功能（缓存、并行、流式调用等），可以看[完整版文档](./how_to_write_async_op_advanced.md)。

---

### 1. 注册 Op

首先，你需要用 `@C.register_op()` 装饰器注册你的 Op：

```python
from flowllm.core.context import C
from flowllm.core.op import BaseAsyncOp

@C.register_op()
class MyAsyncOp(BaseAsyncOp):
    async def async_execute(self):
        # 这里写你的业务逻辑
        return "ok"
```

---

### 2. 读取输入

Op 的输入都放在内部的 `context` 里。调用的时候直接传参数：`await op.async_call(a=1, b=2)`，这些会自动注入到 context。

在 `async_execute()` 里读取：

```python
@C.register_op()
class SumOp(BaseAsyncOp):
    async def async_execute(self):
        # 方式1：直接用 key 访问（没有会抛 KeyError）
        a = self.context["a"]
        b = self.context["b"]
        
        # 方式2：用 get 方法（没有返回默认值）
        a = self.context.get("a", 0)
        b = self.context.get("b", 0)
        
        return a + b

# 调用：
# result = await SumOp().async_call(a=1, b=2)
```

---

### 3. 使用 Prompt 和 LLM

`BaseAsyncOp` 已经帮你把 Prompt 和 LLM 集成好了，直接用就行。

#### 3.1 Prompt 文件

系统会根据你的 Op 文件名自动找对应的 prompt 文件：
- 规则：把 Op 文件名的 `op.py` 后缀换成 `prompt.yaml`，放在同一个目录下
- 比如：`my_feature_op.py` → `my_feature_prompt.yaml`

用的时候：
- `self.prompt_format("prompt_name", **vars)` - 渲染 prompt 模板

#### 3.2 调用 LLM

```python
from flowllm.core.context import C
from flowllm.core.op import BaseAsyncOp
from flowllm.core.schema import Message
from flowllm.core.enumeration import Role
from flowllm.main import FlowLLMApp

@C.register_op()
class QAOp(BaseAsyncOp):
    async def async_execute(self):
        # 1. 读取输入
        question = self.context.get("question", "")
        
        # 2. 渲染 prompt 模板
        prompt = self.prompt_format("qa", question=question)
        
        # 3. 调用 LLM
        messages = [Message(role=Role.USER, content=prompt)]
        answer_message = await self.llm.achat(messages)
        answer = answer_message.content
        
        # 4. 写回输出（见下一节）
        self.context.response.answer = answer
        return answer

# 使用（需要在应用上下文里）
async def main():
    async with FlowLLMApp() as app:
        result = await QAOp().async_call(question="你好？")
        print(result)
```

注意：调用 LLM 需要在应用上下文 `FlowLLMApp()` 里，这样服务配置才能正确加载。

---

### 4. 写输出

输出有两种方式：

```python
@C.register_op()
class QAOp(BaseAsyncOp):
    async def async_execute(self):
        question = self.context.get("question", "")
        prompt = self.prompt_format("qa", question=question)
        messages = [Message(role=Role.USER, content=prompt)]
        answer_message = await self.llm.achat(messages)
        answer = answer_message.content
        
        # 方式1：直接返回
        return answer
        
        # 方式2：写回 context（推荐，便于上层使用）
        self.context.response.answer = answer
        return answer
```

推荐同时使用两种方式：既返回结果，也写回 `context.response.answer`，这样上层可以直接用。

---

### 5. 完整示例

看一个完整的例子：

```python
from flowllm.core.context import C
from flowllm.core.op import BaseAsyncOp
from flowllm.core.schema import Message
from flowllm.core.enumeration import Role
from flowllm.main import FlowLLMApp
import asyncio

@C.register_op()
class SimpleChatOp(BaseAsyncOp):
    async def async_execute(self):
        # 1. 读取输入
        question = self.context.get("question", "")
        
        # 2. 渲染 prompt
        prompt = self.prompt_format("chat", question=question)
        
        # 3. 调用 LLM
        messages = [Message(role=Role.USER, content=prompt)]
        answer_message = await self.llm.achat(messages)
        answer = answer_message.content
        
        # 4. 写回输出
        self.context.response.answer = answer
        return answer

# 使用
async def main():
    async with FlowLLMApp() as app:
        result = await SimpleChatOp().async_call(question="你好？")
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 6. 参考示例

想看实际例子的话，可以看看：
- `flowllm/flowllm/gallery/gen_system_prompt_op.py` - 简单的 LLM 调用示例
- `flowllm/flowllm/gallery/mock_search_op.py` - 使用 callback_fn 的示例

想看更复杂的功能（缓存、并行、流式调用、工具调用等），请查看[完整版文档](./how_to_write_async_op_advanced.md)。

