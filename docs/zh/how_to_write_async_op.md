## 编写异步 Op 指南（基于 BaseAsyncOp）

本文面向需要编写“异步能力”的开发者，指导如何基于 `BaseAsyncOp` 实现一个异步 Op，并涵盖：
- 读取 Op 输入
- 写回 Op 输出
- 使用 prompt（PromptHandler）、LLM / Embedding / Vector Store、缓存（cache）、异步并行
- 如何为 Op 编写测试

参考示例：
- 代码：`flowllm/flowllm/gallery/*.py`（如 `execute_code_op.py`、`stream_chat_op.py`、`gen_system_prompt_op.py`）
- 测试：`flowllm/tests_op/*.py`

---

### 1. 最小骨架与调用方式

最小骨架：仅实现 `async_execute()`，通过 `await op.async_call(**kwargs)` 触发异步执行。

```python
from flowllm.core.op.base_async_op import BaseAsyncOp

class MyAsyncOp(BaseAsyncOp):
    async def async_execute(self):
        # 业务逻辑（异步）
        return "ok"

# 使用（两种方式）
# 1) 直接传入上下文字段：会自动写入到内部 context 中
# result = await MyAsyncOp().async_call(user_id=123)
# 2) 也可以自己构造 FlowContext 再传入：
# result = await MyAsyncOp().async_call(context=FlowContext(user_id=123))
```

---

### 2. 怎么读取 Op 的输入

Op 的输入来自内部 `context`；你可以：
- 在调用时通过 `await op.async_call(a=1, b=2)` 直接注入键值；
- 或在调用时传入你自建的 `FlowContext`。

在 `async_execute()` 中读取：`value = self.context["key"]`，并自行兜底或抛错。

示例：

```python
class SumOp(BaseAsyncOp):
    async def async_execute(self):
        if "a" not in self.context or "b" not in self.context:
            raise ValueError("a/b 为必需输入")
        return self.context["a"] + self.context["b"]

# 调用：
# result = await SumOp().async_call(a=1, b=2)
```

---

### 3. 怎么写 Op 的输出

输出的两种常见方式：
- 返回值：`return result`（`async_call` 的返回值）
- 写回上下文：
  - 写入任意键：`self.context["sum"] = result`
  - 写入最终服务级别的返回：`self.context.response.answer = str(result)`

示例：

```python
class SumOp(BaseAsyncOp):
    async def async_execute(self):
        a = self.context.get("a", 0)
        b = self.context.get("b", 0)
        result = a + b
        # 写回自定义键
        self.context["sum"] = result
        # 写回最终答案（便于上层直接使用）
        self.context.response.answer = str(result)
        return result
```

在工具类场景（需要 Schema 自动映射）建议基于 `BaseAsyncToolOp`，其会根据 `ToolCall` 自动从 `context` 取入参与回填出参。

---

### 4. 使用 PromptHandler、LLM、Embedding、Vector Store

`BaseAsyncOp` 已集成 Prompt 与模型/存储的延迟初始化，可直接使用：

- Prompt：
  - `self.prompt.get_prompt(prompt_name)` 读取模板
  - `self.prompt_format(prompt_name, **vars)` 渲染变量
- LLM：`self.llm`（来自 `C.service_config.llm` 的默认或指定后端）
- Embedding：`self.embedding_model`
- 向量库：`self.vector_store`

#### 4.1 Prompt 与 Op 文件的对应与命名约定

在 `BaseOp` 中，若未显式传入 `prompt_path`，系统会根据 Op 源文件名自动推导默认的 prompt 文件路径：
- 规则：将 Op 源文件名的后缀 `op.py` 替换为 `prompt.yaml`，并放在与 Op 相同的目录下。
- 示例：
  - `my_feature_op.py` → `my_feature_prompt.yaml`
  - `chat_op.py` → `chat_prompt.yaml`

如需自定义路径或文件名，可在实例化 Op 时传入 `prompt_path` 参数进行覆盖：

```python
op = MyAsyncOp(prompt_path="/abs/or/relative/path/to/custom_prompt.yaml")
```

渲染与读取：
- 读取模板：`self.get_prompt("prompt_name")`
- 渲染变量：`self.prompt_format("prompt_name", **vars)`

示例（生成问答）：如涉及 LLM 调用，建议置于应用上下文中使用，保证服务配置正确加载：

```python
from flowllm.main import FlowLLMApp

class QAOp(BaseAsyncOp):
    async def async_execute(self):
        # 读取 prompt 模板并渲染
        question = self.context.get("question", "")
        prompt = self.prompt_format("qa", question=question)

        # 调用 LLM（伪接口，具体参考你项目中的 BaseLLM 实现）
        answer = await self.llm.async_chat(prompt)

        # 写回
        self.context.response.answer = answer
        return answer

async def main():
    async with FlowLLMApp() as app:
        result = await QAOp().async_call(question="你好？")
        print(result)
```

如需用 Embedding 与 Vector Store：

```python
class SearchOp(BaseAsyncOp):
    async def async_execute(self):
        query = self.context.get("query", "")
        query_vec = await self.embedding_model.async_embed(query)
        docs = await self.vector_store.async_search(query_vec, top_k=5)
        self.context["docs"] = docs
        return docs
```

注意：具体的 `async_*` API 名称以实际实现为准（本段为示意）。

---

### 5. 使用缓存（cache）

对于稳定可复用的子任务，使用 `async_save_load_cache(key, fn)` 可显著加速：

```python
class CachedOp(BaseAsyncOp):
    def __init__(self, **kwargs):
        super().__init__(enable_cache=True, cache_expire_hours=1, **kwargs)

    async def _expensive_async_fn(self):
        # 执行耗时任务
        return "heavy-result"

    async def async_execute(self):
        result = await self.async_save_load_cache("heavy_key", self._expensive_async_fn)
        self.context.response.answer = result
        return result
```

`async_save_load_cache` 同时支持同步函数：会自动在线程池中执行（无需你手动封装）。

---

### 6. 异步并行（任务并发）

当 `async_execute` 内需要并发执行多个子任务时：
1) 使用 `self.submit_async_task(coro_fn, *args, **kwargs)` 提交协程任务
2) 使用 `await self.join_async_task(timeout=..., return_exceptions=True)` 汇总结果

```python
import asyncio

class ParallelFetchOp(BaseAsyncOp):
    async def _fetch(self, url: str):
        # 自行替换为真实异步 HTTP 客户端
        await asyncio.sleep(0.01)
        return {"url": url, "status": 200}

    async def async_execute(self):
        urls = self.context.get("urls", [])
        for url in urls:
            self.submit_async_task(self._fetch, url)

        results = await self.join_async_task(timeout=5.0, return_exceptions=True)
        # 过滤异常并写回
        ok = [r for r in results if not isinstance(r, Exception)]
        self.context["fetch_results"] = ok
        return ok
```

注意：
- `submit_async_task` 只接收协程函数；若传入普通函数会被忽略并告警。
- `join_async_task` 支持超时；超时或异常时会取消剩余任务并清理。

---

### 7. 如何进行 Op 测试

推荐使用应用上下文进行快速验证：`async with FlowLLMApp(): ...`。这样会自动加载默认配置（或你指定的配置），并初始化全局服务对象，便于 LLM / Embedding / Vector Store 等组件正常工作。

核心步骤：
- 在应用上下文内构造 `FlowContext`，写入必要输入
- 调用 `await op.async_call(context)`
- 检查返回值与 `context` 的写回键（如 `response.answer`）

最小示例：

```python
import asyncio
from flowllm.main import FlowLLMApp
from flowllm.core.context import FlowContext
from flowllm.core.op.base_async_op import BaseAsyncOp

class SumOp(BaseAsyncOp):
    async def async_execute(self):
        a = self.context.get("a", 0)
        b = self.context.get("b", 0)
        result = a + b
        self.context["sum"] = result
        self.context.response.answer = str(result)
        return result

async def main():
    async with FlowLLMApp() as app:  # 可传入 config_path 或参数覆盖默认配置
        ctx = FlowContext()
        ctx["a"], ctx["b"] = 1, 2
        op = SumOp()
        result = await op.async_call(context=ctx)

        print("result=", result)
        print("sum=", ctx["sum"])
        print("answer=", ctx.response.answer)

asyncio.run(main())
```

更多可对照的工程化案例：
- `flowllm/tests_op/test_execute_code_op.py`（结构与断言思路）
- `flowllm/tests_op/test_stream_chat_op.py`
- `flowllm/tests_op/test_gen_system_prompt_op.py`

---

### 8. 实战建议

- 明确输入契约：在 `async_before_execute` 校验并早失败
- 输出统一写回：使用固定键或 `response.answer` 便于上层编排
- 善用缓存：对“确定性且代价高”的步骤使用缓存
- 并发有度：为 `join_async_task` 设置合理 `timeout` 并处理异常
- Prompt/模型/向量库：确保 `C.service_config` 配置齐全，类属性懒加载按需使用


