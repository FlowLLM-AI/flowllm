# Op 体系介绍

这篇文章会用最简单直白的方式，带你了解 flowllm 中的 Op（算子）体系。我们会看看它们是怎么继承的，各自有什么特点，以及什么时候该用哪个。

## 继承关系总览

先来看看整个家族的继承关系，就像家谱一样：

```
BaseOp（基类Op）
 ├─ BaseAsyncOp（异步Op）
 │   ├─ SequentialOp（顺序Op）
 │   ├─ ParallelOp（并行Op）
 │   └─ BaseAsyncToolOp（工具Op）
 │       └─ BaseMcpOp（MCPOp）
 └─ BaseRayOp（分布式Op）
```

简单来说：

- BaseOp 是所有算子的基类，提供了重试、缓存、上下文管理等基础能力
- BaseAsyncOp 在 BaseOp 基础上加了异步能力，包括异步生命周期钩子和任务编排
- SequentialOp 和 ParallelOp 是用来组合多个算子的，一个按顺序执行，一个并行执行。

#### 重要提示

这两个 Op 不是用来继承的，而是通过 `>>` 或 `|` 运算符自动组合出来的。

- BaseAsyncToolOp 是专门做工具调用的Op，可以按照 Schema 自动处理输入输出
- BaseMcpOp 是调用外部 MCP 工具的，会自动加载 Schema 并调用服务
- BaseRayOp 是用来做分布式并行处理的，适合处理大量数据

## 各 Op 对比表格

下面这个表格从不同维度对比了各个 Op，帮你快速找到合适的：

| Op 类型           | 执行模式       | 主要能力                         | 核心参数                                                                                        | 适合场景                    | 组合能力                   |
|-----------------|------------|------------------------------|---------------------------------------------------------------------------------------------|-------------------------|------------------------|
| BaseOp          | 同步         | 基础功能：重试、缓存、上下文管理、资源延迟初始化     | `async_mode`, `max_retries`, `enable_cache`, `llm`, `embedding_model`                       | 简单的同步，需要基础功能支持          | 支持 `<<`, `>>`, `\|` 组合 |
| BaseAsyncOp     | 异步         | 异步生命周期钩子、异步缓存、任务提交和汇总        | 继承 BaseOp 所有参数                                                                              | 需要异步执行的任务，需要任务编排        | 支持 `<<`, `>>`, `\|` 组合 |
| SequentialOp    | 同步/异步（需一致） | 顺序执行多个子算子，共享上下文              | 通过 `>>` 运算符自动组合（不用于继承）                                                                      | 需要按顺序执行多个步骤的流程          | 不支持 `<<`，用 `>>` 组合     |
| ParallelOp      | 同步/异步（需一致） | 并行执行多个子算子，共享上下文              | 通过 `\|` 运算符自动组合（不用于继承）                                                                      | 需要同时执行多个独立任务            | 不支持 `<<`，用 `\|` 组合     |
| BaseAsyncToolOp | 异步         | 基于 Schema 自动读取输入、写回输出，支持字段映射 | `tool_index`, `save_answer`, `input_schema_mapping`, `output_schema_mapping`                | 需要定义明确输入输出 Schema 的工具调用 | 支持 `<<`, `>>`, `\|` 组合 |
| BaseMcpOp       | 异步         | 调用外部 MCP 工具，自动加载 Schema      | `mcp_name`, `tool_name`, `max_retries`, `timeout`, `input_schema_required/optional/deleted` | 需要调用外部 MCP 服务的场景        | 支持 `<<`, `>>`, `\|` 组合 |
| BaseRayOp       | 同步高并发      | 分布式并行处理，自动识别并行维度，共享大型数据结构    | `ray_max_workers`                                                                           | 需要处理大量数据，需要分布式加速        | 支持 `<<`, `>>`, `\|` 组合 |

## 详细介绍每个 Op

### BaseOp - 最基础的老祖宗

#### 它是什么

所有算子的基类，提供了最基础的能力。

#### 它能做什么

- 标记是同步模式还是异步模式（通过 `async_mode` 控制）
- 提供重试机制（`max_retries`）和异常处理（`raise_exception`）
- 支持缓存功能（`enable_cache`），可以设置过期时间
- 提供上下文管理（`context`）和计时功能（`timer`）
- 延迟初始化 LLM、Embedding 模型、向量库等资源
- 提供组合运算符：`<<`（添加子算子）、`>>`（顺序执行）、`|`（并行执行）

#### 什么时候用它

- 写一个简单的同步或异步任务
- 需要基础的重试、缓存、上下文管理功能
- 作为其他更复杂 Op 的基类

#### 注意事项

- 需要实现 `execute()` 方法（同步）或 `async_execute()` 方法（异步）
- 如果设置了 `max_retries > 1` 或 `raise_exception=False`，失败时会调用 `default_execute()` 作为兜底

---

### BaseAsyncOp - 异步能力增强版

#### 它是什么

在 BaseOp 基础上加了完整的异步能力。

#### 它能做什么

- 继承 BaseOp 的所有能力
- 默认就是异步模式（`async_mode=True`）
- 提供异步生命周期钩子：`async_before_execute()`、`async_execute()`、`async_after_execute()`、`async_default_execute()`
- 支持异步缓存（`async_save_load_cache()`），可以处理协程或在线程池执行同步函数
- 提供任务编排：`submit_async_task()` 提交任务，`join_async_task()` 等待结果，支持超时和异常处理

#### 什么时候用它

- 需要异步执行的任务
- 需要在执行前后做一些异步操作（比如异步读取数据、异步写入结果）
- 需要提交多个异步任务并等待它们完成

#### 注意事项

- 必须实现 `async_execute()` 方法

---

### SequentialOp - 顺序执行组合器

#### 它是什么

用来按顺序执行多个算子的组合器。

#### 重要认知

这个 Op 不是用来继承的，而是通过 `>>` 运算符自动组合出来的。

#### 它能做什么

- 按顺序执行多个子算子，前一个的输出作为后一个的输入
- 所有子算子共享同一个 `context`
- 当你使用 `op1 >> op2` 时，会自动创建一个 `SequentialOp` 实例
- 支持同步和异步两种模式，但所有子算子的模式必须一致

#### 什么时候用它

- 需要按顺序执行多个步骤的流程
- 比如：先搜索 → 再总结 → 最后生成报告
- 使用方式：`op1 >> op2 >> op3`，系统会自动创建 `SequentialOp` 来组合它们

#### 注意事项

- 不要直接继承 SequentialOp，而是通过 `>>` 运算符来组合算子
- 不能用 `<<` 运算符（会报错）
- 所有子算子的 `async_mode` 必须一致
- 返回最后一个算子的结果

---

### ParallelOp - 并行执行组合器

#### 它是什么

用来并行执行多个算子的组合器。

#### 重要认知

这个 Op 不是用来继承的，而是通过 `|` 运算符自动组合出来的。

#### 它能做什么

- 同时执行多个子算子，所有子算子共享同一个 `context`
- 当你使用 `op1 | op2` 时，会自动创建一个 `ParallelOp` 实例
- 支持同步（多线程）和异步（asyncio）两种模式，但所有子算子的模式必须一致
- 返回所有子算子结果的列表

#### 什么时候用它

- 需要同时执行多个独立的任务
- 比如：同时调用多个搜索接口、同时处理多个文件
- 使用方式：`op1 | op2 | op3`，系统会自动创建 `ParallelOp` 来组合它们

#### 注意事项

- 不要直接继承 ParallelOp，而是通过 `|` 运算符来组合算子
- 不能用 `<<` 运算符（会报错）
- 所有子算子的 `async_mode` 必须一致
- 返回的是列表，包含所有子算子的结果

---

### BaseAsyncToolOp - 工具调用专用

#### 它是什么

专门用来做工具调用的，可以按照 Schema 自动处理输入输出。

#### 它能做什么

- 通过 `build_tool_call()` 定义工具的 Schema（描述、输入参数、输出参数）
- 自动从 `context` 中读取输入参数（按照输入 Schema）
- 自动把输出结果写回 `context`（按照输出 Schema）
- 支持字段映射（`input_schema_mapping`、`output_schema_mapping`）
- 支持多个工具实例（通过 `tool_index` 区分）
- 可以选择是否把主要输出写入 `response.answer`

#### 什么时候用它

- 需要定义明确输入输出 Schema 的工具
- 比如：搜索工具（输入：查询词，输出：搜索结果）、翻译工具（输入：文本，输出：翻译结果）

#### 注意事项

- 必须实现 `build_tool_call()` 和 `async_execute()` 方法
- 如果没有定义输出 Schema，会自动创建一个单字符串输出
- 输入参数如果标记为 `required=True`，在 `context` 中找不到会报错

---

### BaseMcpOp - 外部 MCP 工具调用

#### 它是什么

专门用来调用外部 MCP（Model Context Protocol）工具的。

#### 它能做什么

- 从服务配置中自动加载工具的 Schema（`C.external_mcp_tool_call_dict[mcp_name][tool_name]`）
- 可以覆盖 Schema 中的参数要求（`input_schema_required`、`input_schema_optional`、`input_schema_deleted`）
- 使用 `FastMcpClient` 调用外部 MCP 服务
- 支持重试（`max_retries`）和超时（`timeout`）
- 自动处理输入输出（继承自 BaseAsyncToolOp）

#### 什么时候用它

- 需要调用外部 MCP 服务的场景
- 比如：调用阿里云的 MCP 工具、调用其他第三方 MCP 服务

#### 注意事项

- 需要在服务配置中配置好 `external_mcp` 和对应的工具 Schema
- 默认 `raise_exception=False`，失败不会抛异常
- 默认 `max_retries=3`，会自动重试

---

### BaseRayOp - 分布式并行处理

#### 它是什么

用来做分布式并行处理的，适合处理大量数据。

#### 它能做什么

- 自动识别 `kwargs` 中的第一个列表参数作为并行维度（也可以显式指定 `parallel_key`）
- 通过 Ray 把任务分发到多个 worker 上执行
- 自动把大型数据结构（DataFrame、Series、dict、list、Context）转换成 Ray 对象共享，避免重复传输
- 按照 `ray_max_workers` 创建 worker，用轮询切片的方式分配任务
- 最后把所有结果汇总并扁平化

#### 什么时候用它

- 需要处理大量数据，比如处理几千条记录
- 需要分布式加速，比如批量调用 LLM、批量处理文件

#### 注意事项

- 需要在服务配置中设置 `ray_max_workers > 1`
- 第一次调用会自动初始化 Ray（如果还没初始化）
- 会自动识别列表参数，但如果有多个列表，最好显式指定 `parallel_key`

