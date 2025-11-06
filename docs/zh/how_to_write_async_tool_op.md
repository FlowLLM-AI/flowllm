## 编写异步 Tool Op 指南 (BaseAsyncToolOp)

本文简明说明 `BaseAsyncToolOp` 相比 `BaseAsyncOp` 的“不同点/额外能力”，便于你快速上手基于 Schema 的工具类异步 Op。可参考示例 `flowllm/flowllm/gallery/execute_code_op.py`。

### 1. 核心差异概览

- **Schema 驱动的输入/输出**：通过实现 `build_tool_call()` 返回 `ToolCall`，描述工具的 `description`、`input_schema`、（可选）`output_schema`。
  - 运行时会根据 `input_schema` 自动从 `context` 读取输入到 `self.input_dict`。
  - 执行完成后会把 `self.output_dict` 自动写回 `context`（键名来自 `output_schema`）。
- **便捷输出设置**：提供 `set_output(value, key="")` 和 `set_outputs(**kwargs)`，无需手动管理 `output_dict` 键名（单输出时可省略 `key`）。
- **自动应答写回**：`save_answer=True` 时，会将主输出写入 `context.response.answer`；多输出时会写入其 JSON 字符串。
- **索引化多实例**：`tool_index` 会在上下文键后追加后缀（如 `result.1`），便于在同一上下文中多次调用同一工具。
- **键名映射**：`input_schema_mapping` / `output_schema_mapping` 可将 Schema 键与 `context` 键进行映射（当两者命名不一致时很有用）。

你仍然只需实现：
- `def build_tool_call(self) -> ToolCall`
- `async def async_execute(self)`（业务逻辑中从 `self.input_dict` 取输入，使用 `set_output`/`set_outputs` 写出）

### 2. 最小示例（参考 execute_code_op）

```python
from flowllm.core.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.core.schema import ToolCall, ParamAttrs

class EchoToolOp(BaseAsyncToolOp):
    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            description="Echo input text",
            input_schema={
                "text": ParamAttrs(type="str", description="text to echo", required=True),
            },
            # 可选：如不提供 output_schema，则会生成默认的单字符串输出键 `${short_name}_result`
        )

    async def async_execute(self):
        # 读取输入（由框架在执行前已从 context 填充到 self.input_dict）
        text = self.input_dict.get("text", "")
        # 设置输出（会在执行后自动写回 context）
        self.set_output(text)

# 触发执行（示意）：
# await EchoToolOp().async_call(text="hello")
# 执行后：
# - context 中将写入默认输出键，如 "echo_tool_op_result": "hello"（具体以 short_name 为准）
# - 若 save_answer=True，还会写入 context.response.answer
```

更完整的工具示例请参考：
- `flowllm/flowllm/gallery/execute_code_op.py`

### 3. 与 BaseAsyncOp 的对照

| 能力 | BaseAsyncOp | BaseAsyncToolOp |
| --- | --- | --- |
| 输入读取 | 手动从 `self.context[...]` 读取 | 根据 `input_schema` 自动填充 `self.input_dict` |
| 输出写回 | 手动写 `self.context[...]` / `response.answer` | `set_output(s)` 写入 `self.output_dict`，自动写回上下文；可自动写 `response.answer` |
| Schema 描述 | 无内建 | 通过 `build_tool_call()` 描述输入输出与说明 |
| 多实例区分 | 自行约定 | 通过 `tool_index` 自动为上下文键追加后缀 |
| 键名映射 | 自行处理 | `input_schema_mapping` / `output_schema_mapping` 内建映射能力 |

结论：当你的 Op 本质是“工具”（有清晰的输入/输出契约、希望自动化 IO 与应答写回），应优先选择 `BaseAsyncToolOp`；否则选择通用的 `BaseAsyncOp` 并手动处理 IO。


