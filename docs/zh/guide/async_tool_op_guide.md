## 异步 Tool Op 指南 (BaseAsyncToolOp)

这是一个完整的示例，展示如何使用 `BaseAsyncToolOp` 编写基于 Schema 的工具类异步 Op。相比 `BaseAsyncOp`，`BaseAsyncToolOp` 提供了 Schema 驱动的输入/输出自动处理能力。

---

### 完整示例

#### Op 文件：`echo_tool_op.py`

```python
import asyncio

from flowllm.core.context import C
from flowllm.core.op import BaseAsyncToolOp
from flowllm.core.schema import ToolCall
from flowllm.main import FlowLLMApp


@C.register_op()
class EchoToolOp(BaseAsyncToolOp):
    """简单的 Echo 工具 Op，展示 BaseAsyncToolOp 的基本用法"""

    def build_tool_call(self) -> ToolCall:
        """定义工具的 Schema：描述、输入参数、输出参数"""
        return ToolCall(
            **{
                "description": "Echo input text, returns the same text as output",
                "input_schema": {
                    "text": {
                        "type": "str",
                        "description": "text to echo",
                        "required": True,
                    },
                },
            }
        )

    async def async_execute(self):
        """执行工具逻辑"""
        # 1. 读取输入（由框架在执行前已从 context 填充到 self.input_dict）
        text = self.input_dict.get("text", "")

        # 2. 处理逻辑
        result = f"Echo: {text}"

        # 3. 设置输出（会在执行后自动写回 context）
        # 单输出时可以省略 key 参数
        self.set_output(result)

        # 或者使用 set_outputs 设置多个输出：
        # self.set_outputs(result=result, length=len(text))


# 使用示例
async def main():
    async with FlowLLMApp() as app:
        # 基本使用
        result = await EchoToolOp().async_call(text="hello")
        print(f"结果：{result}")

        # 执行后，context 中会自动写入：
        # - "echo_tool_op_result": "Echo: hello"（默认输出键名）
        # - context.response.answer = "Echo: hello"（如果 save_answer=True）


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 核心特性

#### 1. Schema 驱动的输入/输出

- **定义 Schema**：通过 `build_tool_call()` 返回 `ToolCall`，描述工具的：
  - `description`：工具描述
  - `input_schema`：输入参数定义（类型、描述、是否必需）
  - `output_schema`：输出参数定义（可选，不提供时会自动生成）

- **自动输入读取**：运行时会根据 `input_schema` 自动从 `context` 读取输入到 `self.input_dict`
- **自动输出写回**：执行完成后会把 `self.output_dict` 自动写回 `context`（键名来自 `output_schema`）

#### 2. 便捷的输出设置方法

- **`set_output(value, key="")`**：设置单个输出值
  - 单输出时可以省略 `key` 参数
  - 多输出时必须指定 `key`

- **`set_outputs(**kwargs)`**：设置多个输出值

#### 3. 自动应答写回

- `save_answer=True`（默认）时，会将主输出写入 `context.response.answer`
- 单输出：直接写入字符串
- 多输出：写入 JSON 字符串

#### 4. 多实例支持

- `tool_index` 参数可以在上下文键后追加后缀（如 `result.1`）
- 便于在同一上下文中多次调用同一工具

#### 5. 键名映射

- `input_schema_mapping`：将 Schema 输入键映射到 context 键
- `output_schema_mapping`：将 Schema 输出键映射到 context 键
- 当 Schema 键名与 context 键名不一致时很有用

---

### 与 BaseAsyncOp 的对比

| 能力        | BaseAsyncOp                                 | BaseAsyncToolOp                                                      |
|-----------|---------------------------------------------|----------------------------------------------------------------------|
| 输入读取      | 手动从 `self.context[...]` 读取                  | 根据 `input_schema` 自动填充 `self.input_dict`                             |
| 输出写回      | 手动写 `self.context[...]` / `response.answer` | `set_output(s)` 写入 `self.output_dict`，自动写回上下文；可自动写 `response.answer` |
| Schema 描述 | 无内建                                         | 通过 `build_tool_call()` 描述输入输出与说明                                     |
| 多实例区分     | 自行约定                                        | 通过 `tool_index` 自动为上下文键追加后缀                                          |
| 键名映射      | 自行处理                                        | `input_schema_mapping` / `output_schema_mapping` 内建映射能力              |

**选择建议**：
- 当你的 Op 本质是"工具"（有清晰的输入/输出契约、希望自动化 IO 与应答写回），应优先选择 `BaseAsyncToolOp`
- 否则选择通用的 `BaseAsyncOp` 并手动处理 IO

---

### 关键要点

1. **必须实现的方法**：
   - `build_tool_call()`：返回 `ToolCall` 对象，定义工具的 Schema
   - `async_execute()`：实现工具的业务逻辑

2. **输入处理**：
   - 从 `self.input_dict` 读取输入（框架已自动填充）
   - 如果 `required=True` 的输入在 context 中找不到，会抛出异常

3. **输出处理**：
   - 使用 `self.set_output(value, key="")` 或 `self.set_outputs(**kwargs)` 设置输出
   - 框架会自动将输出写回 context 和 response.answer

4. **输出键名规则**：
   - 如果定义了 `output_schema`，使用 Schema 中定义的键名
   - 如果没有定义 `output_schema`，自动生成 `${short_name}_result` 作为键名

5. **多实例使用**：
   - 设置 `tool_index` 参数区分多个实例
   - 输出键会自动追加 `.{tool_index}` 后缀

6. **键名映射**：
   - 使用 `input_schema_mapping` 和 `output_schema_mapping` 进行键名映射
   - 例如：`input_schema_mapping={"text": "query"}` 表示从 context 的 `query` 键读取，但映射到 `input_dict` 的 `text` 键

---

### 参考示例

实际项目中的示例：

- `flowllm/flowllm/gallery/execute_code_op.py` - 代码执行工具的完整示例
- `flowllm/flowllm/core/op/base_async_tool_op.py` - BaseAsyncToolOp 基类实现
- `flowllm/flowllm/core/op/base_mcp_op.py` - MCP 工具调用示例（继承自 BaseAsyncToolOp）

