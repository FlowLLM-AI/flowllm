## 编写异步 Op 完整指南（进阶版）

这篇文档涵盖异步 Op 的所有高级功能。如果你是新手，建议先看[简单版文档](./how_to_write_async_op_simple.md)了解基础用法。

---

### 1. Context 的常用属性

除了用 `self.context["key"]` 读取，`context` 还有一些常用属性可以直接访问：

```python
class MyOp(BaseAsyncOp):
    async def async_execute(self):
        # 常用属性
        query = self.context.query  # 用户查询
        messages = self.context.messages  # 消息列表
        system_prompt = self.context.system_prompt  # 系统提示词
        response = self.context.response  # 响应对象
```

---

### 2. BaseAsyncToolOp 的使用

如果你写的是工具类的 Op（需要 Schema 自动映射），建议用 `BaseAsyncToolOp`：

- 输入会自动从 `context` 提取到 `self.input_dict` 里
- 输出用 `self.set_output(value)` 或 `self.set_outputs(**kwargs)` 自动写回
- 会根据 `ToolCall` 自动处理输入输出映射

```python
from flowllm.core.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.core.schema import ToolCall, ParamAttrs

@C.register_op()
class EchoToolOp(BaseAsyncToolOp):
    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            description="Echo input text",
            input_schema={
                "text": ParamAttrs(type="str", description="text to echo", required=True),
            },
        )

    async def async_execute(self):
        # 输入自动在 self.input_dict 里
        text = self.input_dict.get("text", "")
        
        # 输出用 set_output
        self.set_output(text)
```

更多细节请参考 `how_to_write_async_tool_op.md`。

---

### 3. 用 callback_fn 处理 LLM 响应

有时候 LLM 返回的内容需要提取或者转换，可以用 `callback_fn` 来处理：

```python
from flowllm.core.utils.common_utils import extract_content
import json

@C.register_op()
class SearchOp(BaseAsyncOp):
    async def async_execute(self):
        query = self.context.query
        prompt = self.prompt_format("search_prompt", query=query)
        messages = [Message(role=Role.USER, content=prompt)]

        # 用 callback_fn 从响应中提取 JSON 内容
        def callback_fn(message: Message):
            return extract_content(message.content, "json")

        # callback_fn 的返回值会作为 achat 的返回值
        search_results = await self.llm.achat(messages, callback_fn=callback_fn)
        self.context.response.answer = json.dumps(search_results, ensure_ascii=False)
        return search_results
```

---

### 4. 调用 LLM 时传入工具（tools）

如果 LLM 需要调用工具，可以传入 `tools` 参数：

```python
@C.register_op()
class ReactOp(BaseAsyncOp):
    async def async_execute(self):
        # 获取其他 op 作为工具（从 self.ops 里拿）
        if "search" in self.ops:
            search_op = self.ops["search"]
        else:
            from .dashscope_search_op import DashscopeSearchOp
            search_op = DashscopeSearchOp()
        
        # 把 op 的 tool_call 传给 LLM
        tools = [search_op.tool_call]
        messages = [Message(role=Role.USER, content=query)]
        
        # LLM 可能会返回 tool_calls，需要执行这些工具
        assistant_message = await self.llm.achat(messages, tools=tools)
        
        if assistant_message.tool_calls:
            # 执行工具调用...
            for tool_call in assistant_message.tool_calls:
                # 处理每个工具调用
                pass
```

---

### 5. 流式调用（Streaming）

如果需要流式返回 LLM 的响应，可以用 `astream_chat`，然后用 `context.add_stream_chunk` 把每个块发出去：

```python
from flowllm.core.enumeration import ChunkEnum
from flowllm.core.schema import FlowStreamChunk

@C.register_op()
class StreamChatOp(BaseAsyncOp):
    async def async_execute(self):
        messages = self.context.messages
        system_prompt = self.context.system_prompt
        
        # 加上系统提示词
        messages = [Message(role=Role.SYSTEM, content=system_prompt)] + messages
        
        # 流式调用，逐个处理每个 chunk
        async for stream_chunk in self.llm.astream_chat(messages):
            # 只处理需要的 chunk 类型（答案、思考、错误、工具调用等）
            if stream_chunk.chunk_type in [ChunkEnum.ANSWER, ChunkEnum.THINK, ChunkEnum.ERROR, ChunkEnum.TOOL]:
                await self.context.add_stream_chunk(stream_chunk)
```

---

### 6. 使用其他 Op（self.ops）

如果需要在 Op 里调用其他 Op，可以通过 `self.ops` 获取。`self.ops` 是一个字典，键是 op 的名字：

```python
@C.register_op()
class CompositeOp(BaseAsyncOp):
    async def async_execute(self):
        # 从 self.ops 里获取其他 op
        if "search" in self.ops:
            search_op = self.ops["search"]
            # 调用其他 op
            result = await search_op.async_call(query=self.context.query)
            self.context["search_result"] = result
```

---

### 7. 用缓存加速

如果你的任务结果比较稳定，可以复用，用 `async_save_load_cache(key, fn)` 能快很多：

```python
@C.register_op()
class CachedOp(BaseAsyncOp):
    def __init__(self, **kwargs):
        super().__init__(enable_cache=True, cache_expire_hours=1, **kwargs)

    async def _expensive_async_fn(self):
        # 这里执行一些耗时的任务
        return "heavy-result"

    async def async_execute(self):
        result = await self.async_save_load_cache("heavy_key", self._expensive_async_fn)
        self.context.response.answer = result
        return result
```

`async_save_load_cache` 也支持同步函数，会自动在线程池里执行（你不用手动封装）。

---

### 8. 异步并行（同时执行多个任务）

如果 `async_execute` 里需要同时执行多个子任务：
1) 用 `self.submit_async_task(coro_fn, *args, **kwargs)` 提交协程任务
2) 用 `await self.join_async_task(timeout=..., return_exceptions=True)` 等所有任务完成并汇总结果

```python
import asyncio

@C.register_op()
class ParallelFetchOp(BaseAsyncOp):
    async def _fetch(self, url: str):
        # 这里你自己替换成真实的异步 HTTP 客户端
        await asyncio.sleep(0.01)
        return {"url": url, "status": 200}

    async def async_execute(self):
        urls = self.context.get("urls", [])
        for url in urls:
            self.submit_async_task(self._fetch, url)

        results = await self.join_async_task(timeout=5.0, return_exceptions=True)
        # 把异常过滤掉，只保留正常的结果
        ok = [r for r in results if not isinstance(r, Exception)]
        self.context["fetch_results"] = ok
        return ok
```

注意：
- `submit_async_task` 只接收协程函数，如果传普通函数会被忽略并警告
- `join_async_task` 支持超时，超时或者有异常的时候会自动取消剩余任务并清理
- 如果要并行调用多个 Op 实例，记得用 `op.copy()` 复制一下，避免状态冲突

看个更实际的例子（并行调用多个工具）：

```python
@C.register_op()
class ParallelToolOp(BaseAsyncOp):
    async def async_execute(self):
        tool_calls = self.context.get("tool_calls", [])
        op_list = []
        
        for tool_call in tool_calls:
            if tool_call.name in self.ops:
                # 复制 op 避免状态冲突
                op_copy = self.ops[tool_call.name].copy()
                op_list.append(op_copy)
                # 提交任务
                self.submit_async_task(op_copy.async_call, **tool_call.argument_dict)
        
        # 等待所有任务完成
        await self.join_async_task()
        
        # 收集结果
        results = [op.output for op in op_list]
        self.context["tool_results"] = results
        return results
```

---

### 9. 使用 Embedding 和向量库

```python
@C.register_op()
class VectorSearchOp(BaseAsyncOp):
    async def async_execute(self):
        query = self.context.get("query", "")
        
        # 生成 embedding
        query_vec = await self.embedding_model.async_embed(query)
        
        # 向量搜索
        docs = await self.vector_store.async_search(query_vec, top_k=5)
        
        self.context["docs"] = docs
        return docs
```

注意：具体的 `async_*` API 名字以你实际实现的为准。

---

### 10. 自定义 Prompt 路径

如果你想用别的路径或者文件名，创建 Op 的时候传个 `prompt_path` 参数就行：

```python
op = MyAsyncOp(prompt_path="/abs/or/relative/path/to/custom_prompt.yaml")
```

---

### 11. 写回消息列表

如果返回的是对话历史，可以写回 `response.messages`：

```python
@C.register_op()
class ChatOp(BaseAsyncOp):
    async def async_execute(self):
        messages = self.context.messages
        # ... 处理消息 ...
        self.context.response.messages = messages  # 保存对话历史
        return messages
```

---

### 12. 怎么给 Op 写测试

推荐用应用上下文来快速验证：`async with FlowLLMApp(): ...`。这样会自动加载默认配置（或者你指定的配置），并且初始化全局服务对象，LLM、Embedding、向量库这些组件就能正常工作了。

核心步骤：
- 在应用上下文里构造一个 `FlowContext`，把需要的输入写进去
- 调用 `await op.async_call(context)`
- 检查返回值和 `context` 里写回去的键（比如 `response.answer`）

最简单的例子：

```python
import asyncio
from flowllm.main import FlowLLMApp
from flowllm.core.context import FlowContext
from flowllm.core.op.base_async_op import BaseAsyncOp

@C.register_op()
class SumOp(BaseAsyncOp):
    async def async_execute(self):
        a = self.context.get("a", 0)
        b = self.context.get("b", 0)
        result = a + b
        self.context["sum"] = result
        self.context.response.answer = str(result)
        return result

async def main():
    async with FlowLLMApp() as app:  # 可以传 config_path 或者参数来覆盖默认配置
        ctx = FlowContext()
        ctx["a"], ctx["b"] = 1, 2
        op = SumOp()
        result = await op.async_call(context=ctx)

        print("result=", result)
        print("sum=", ctx["sum"])
        print("answer=", ctx.response.answer)

asyncio.run(main())
```

想看更完整的工程化例子，可以看看：
- `flowllm/tests_op/test_execute_code_op.py`（看看结构和断言是怎么写的）
- `flowllm/tests_op/test_stream_chat_op.py`
- `flowllm/tests_op/test_gen_system_prompt_op.py`

---

### 13. 一些实战建议

- **输入要明确**：在 `async_before_execute` 里校验一下，有问题早点报错。可以用 `assert` 或者抛异常
- **输出统一写回**：用固定的键或者 `response.answer`，这样上层编排起来方便。如果返回消息列表，记得写 `response.messages`
- **缓存用起来**：对于结果确定、但执行代价高的步骤，用缓存能省不少时间
- **并发要适度**：给 `join_async_task` 设置个合理的 `timeout`，记得处理异常。并行调用 Op 时记得用 `copy()` 避免状态冲突
- **配置要齐全**：Prompt、模型、向量库这些，确保 `C.service_config` 都配好了，类属性是懒加载的，按需用就行
- **callback_fn 很好用**：如果 LLM 返回的内容需要提取（比如 JSON、代码块），用 `callback_fn` 处理，代码更清晰
- **流式调用记得过滤**：用 `astream_chat` 的时候，记得只处理你需要的 `chunk_type`，别把所有 chunk 都发出去
- **工具类用 BaseAsyncToolOp**：如果你的 Op 本质是工具（有明确的输入输出 Schema），用 `BaseAsyncToolOp` 更省事，自动处理 IO 映射

---

### 14. 参考示例

想看实际例子的话，可以看看：
- `flowllm/flowllm/gallery/execute_code_op.py` - BaseAsyncToolOp 示例
- `flowllm/flowllm/gallery/stream_chat_op.py` - 流式调用示例
- `flowllm/flowllm/gallery/gen_system_prompt_op.py` - callback_fn 使用示例
- `flowllm/flowllm/gallery/react_search_op.py` - 工具调用和并行任务示例
- `flowllm/flowllm/gallery/mock_search_op.py` - callback_fn 和 context.query 示例

