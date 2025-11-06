## Op 体系介绍（按继承关系）

本文基于 `flowllm/core/op` 的实现，按继承关系介绍 Op 体系的职责、关键能力与用法示例，帮助你快速编写、组合与运行算子（Op）。

### 继承关系总览

```
BaseOp
 ├─ BaseAsyncOp
 │   ├─ SequentialOp
 │   ├─ ParallelOp
 │   └─ BaseAsyncToolOp
 │       └─ BaseMcpOp
 └─ BaseRayOp
```

核心要点：
- **BaseOp**：同步/异步模式开关、重试、缓存、上下文、LLM/Embedding/向量库延迟初始化、算子组合运算符。
- **BaseAsyncOp**：提供完整异步生命周期（`async_*` 钩子、任务提交与汇总）。
- **SequentialOp / ParallelOp**：顺序/并行组合多个子算子，复用同一上下文。
- **BaseAsyncToolOp**：按工具 Schema 从上下文取入参、回写出参，可自动写入 `response.answer`。
- **BaseMcpOp**：基于 MCP 的外部工具调用（从服务配置加载 ToolCall Schema 并调用）。
- **BaseRayOp**：Ray 分布式并行，自动根据列表参数切分、分发与汇总结果。

---

### BaseOp（核心基类）
文件：`flowllm/core/op/base_op.py`

职责与能力：
- 执行模式：`async_mode`（与子算子保持一致）
- 重试与异常：`max_retries`、`raise_exception`、`default_execute()` 兜底
- 缓存：`enable_cache`、`save_load_cache()`、`cache_expire_hours`
- 上下文与计时：`build_context()`、`self.context`、`self.timer`
- 资源延迟初始化：`llm`、`embedding_model`、`vector_store`
- 组合运算符：
  - `op << other` 添加子算子（列表/字典均可）
  - `op >> other` 构建顺序执行（返回 `SequentialOp`）
  - `op | other` 构建并行执行（返回 `ParallelOp`）

最小示例（同步）：

```python
from flowllm.core.op.base_op import BaseOp

class HelloOp(BaseOp):
    def execute(self):
        return "hello"

result = HelloOp().call()
```

---

### BaseAsyncOp（异步基类）
文件：`flowllm/core/op/base_async_op.py`

在 `BaseOp` 之上增加：
- 异步生命周期：`async_before_execute()` / `async_execute()` / `async_after_execute()` / `async_default_execute()`
- 异步缓存：`async_save_load_cache()`（支持协程或在线程池中执行的同步函数）
- 任务编排：`submit_async_task()` 与 `join_async_task()`（带超时与异常处理）

最小示例（异步）：

```python
import asyncio
from flowllm.core.op.base_async_op import BaseAsyncOp

class AsyncHelloOp(BaseAsyncOp):
    async def async_execute(self):
        return "hello-async"

async def main():
    print(await AsyncHelloOp().async_call())

asyncio.run(main())
```

---

### SequentialOp（顺序执行）与 ParallelOp（并行执行）
文件：`flowllm/core/op/sequential_op.py`, `flowllm/core/op/parallel_op.py`

共同特性：
- 使用与其模式一致的子算子（同步/异步必须一致），共享同一 `context`。
- 通过 `>>`（顺序）或 `|`（并行）从任意 `BaseOp`/`BaseAsyncOp` 派生算子便捷构造。
- 在这两个类中禁用 `<<`（直接添加子算子），使用对应的运算符叠加。

示例（同步顺序 + 并行）：

```python
from flowllm.core.op.base_op import BaseOp

class A(BaseOp):
    def execute(self):
        return "A"

class B(BaseOp):
    def execute(self):
        return "B"

# 顺序：A >> B
seq = A() >> B()
print(seq.call())

# 并行：A | B（返回列表结果）
par = A() | B()
print(par.call())
```

示例（异步并行）：

```python
import asyncio
from flowllm.core.op.base_async_op import BaseAsyncOp

class A(BaseAsyncOp):
    async def async_execute(self):
        return "A-async"

class B(BaseAsyncOp):
    async def async_execute(self):
        return "B-async"

async def main():
    par = A() | B()
    print(await par.async_call())

asyncio.run(main())
```

注意：顺序/并行组合时，会断言子算子的 `async_mode` 与组合器一致。

---

### BaseAsyncToolOp（基于 Schema 的工具算子）
文件：`flowllm/core/op/base_async_tool_op.py`

职责：
- 由子类实现 `build_tool_call()` 返回工具的 `ToolCall`（包含描述、输入/输出 Schema）。
- 在 `async_before_execute()` 阶段按输入 Schema 从 `context` 取值（支持 `input_schema_mapping` 与 `tool_index` 后缀）。
- 在 `async_after_execute()` 阶段把 `output_dict` 回写到 `context`（支持 `output_schema_mapping`），可选写入 `response.answer`。

关键成员：
- `tool_call`（懒加载，自动补齐默认的单字符串输出）
- `input_dict`/`output_dict`（实际入参/出参值）
- `set_output()`/`set_outputs()`（便捷设置输出）

最小示例：

```python
from flowllm.core.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.core.schema import ToolCall, ParamAttrs

class EchoToolOp(BaseAsyncToolOp):
    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            description="Echo input to output",
            input_schema={
                "text": ParamAttrs(type="str", description="text", required=True),
            },
        )

    async def async_execute(self):
        self.set_output(self.input_dict.get("text", ""))

# 使用时需在 context 中放入 text
```

---

### BaseMcpOp（调用外部 MCP 工具）
文件：`flowllm/core/op/base_mcp_op.py`

特性：
- 从 `C.external_mcp_tool_call_dict[mcp_name][tool_name]` 读取工具的 `ToolCall` Schema，并可通过 `input_schema_required/optional/deleted` 覆盖。
- 使用 `FastMcpClient` 调用外部 MCP 服务，将 `input_dict` 传入，结果通过 `set_output()` 写入。
- 典型配置项：`mcp_name`、`tool_name`、`max_retries`、`timeout`、`save_answer`。

最小示例（伪）：

```python
from flowllm.core.op.base_mcp_op import BaseMcpOp

class SearchOp(BaseMcpOp):
    def __init__(self):
        super().__init__(mcp_name="my_mcp", tool_name="search")

# 需要在服务配置中提供 external_mcp 与对应的 tool schema
```

---

### BaseRayOp（Ray 分布式并行）
文件：`flowllm/core/op/base_ray_op.py`

能力：
- 自动识别 `kwargs` 中的第一个列表参数为并行维度（或显式传入 `parallel_key`）。
- 将大型结构（DataFrame/Series/dict/list/Context）通过 `ray.put` 共享。
- 按 `ray_max_workers` 创建 worker，采用轮询切片 `items[actor_index::max_workers]` 分配任务，最终汇总扁平化结果。

关键方法：
- `submit_and_join_parallel_op(op, **kwargs)`：对另一个 `BaseOp` 进行分布式并行调用。
- `submit_and_join_ray_task(fn, parallel_key=..., **kwargs)`：对任意函数进行并行切分与执行。

最小示例（伪）：

```python
from flowllm.core.op.base_ray_op import BaseRayOp

class MyRayOp(BaseRayOp):
    def execute(self):
        items = list(range(100))
        return self.submit_and_join_ray_task(
            fn=lambda items, x: x * 2,  # 示例：对每个 x 计算 2x
            items=items,                 # 自动识别为并行 key
        )
```

Ray 使用注意：在服务配置中将 `ray_max_workers` 设为大于 1，首次调用会自动 `ray.init()`（若未初始化）。

---

### 常见约束与最佳实践

- 保持组合双方 `async_mode` 一致：顺序/并行组合会断言一致性。
- 失败兜底：当 `max_retries > 1` 或 `raise_exception=False` 时，最终失败会调用 `default_execute()`/`async_default_execute()` 产生默认结果。
- 充分利用缓存：使用 `enable_cache=True` 与 `save_load_cache()` / `async_save_load_cache()`。
- 上下文传递：组合算子共享同一 `context`，工具算子会按 Schema 自动读取与回写。
- Prompt/LLM/Embedding/VectorStore 均为延迟初始化，确保配置 `C.service_config` 正确。


