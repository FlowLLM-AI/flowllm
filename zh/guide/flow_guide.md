## Flow 配置指南

本文详细介绍如何在 `flowllm/flowllm/config/default.yaml` 中配置 Flow（流程）。Flow 是 FlowLLM 的核心概念，通过组合多个 Op（操作）来构建复杂的处理流程。

---

### 一、Flow 配置基础

在配置文件中，`flow` 段用于定义一组可被调用的流程。每个 Flow 的基本结构如下：

```yaml
flow:
  flow_name:
    flow_content: Op1Op() >> Op2Op()
    description: "流程描述"  # 可选
    stream: false  # 可选，是否流式输出
    input_schema:  # 可选，输入字段定义
      field_name:
        type: string
        description: "字段说明"
        required: true
```

**字段说明：**
- `flow_content`: **必需**。Flow 表达式，使用运算符组合多个 Op。
- `description`: **可选**。流程描述，用于文档生成和调试。
- `stream`: **可选**。若为 `true`，表示该流程以流式方式输出（如 SSE/Chunk）。
- `input_schema`: 在不同运行模式下有不同要求：
  - 在 MCP 模式下：**必需** 且需精确定义输入字段（类型、是否必填、描述等），用于参数校验与客户端能力展示。
  - 在 HTTP/Stream 模式下：**可选**；建议提供以便进行入参校验与自动文档生成，但不是强制项。

---

### 二、Flow 表达式语法

Flow 表达式使用 Python 语法，通过运算符组合 Op 实例。表达式会被 `parse_flow_expression` 函数解析成可执行的 Op 树。

#### 2.1 基本运算符

**顺序执行（`>>`）**
- 使用 `>>` 连接多个 Op，表示按顺序执行。
- 前一个 Op 的输出会作为后一个 Op 的输入。

```yaml
flow_content: Op1Op() >> Op2Op() >> Op3Op()
```

**并行执行（`|`）**
- 使用 `|` 连接多个 Op，表示并行执行。
- 所有 Op 同时运行，结果会合并。

```yaml
flow_content: Op1Op() | Op2Op()
```

**混合组合**
- 可以使用括号进行分组，构建复杂的执行流程。

```yaml
flow_content: Op1Op() >> (Op2Op() | Op3Op()) >> Op1Op()
```

#### 2.2 单行表达式

最简单的 Flow 表达式是单行，直接使用运算符连接 Op：

```yaml
flow:
  simple_flow:
    flow_content: GenSystemPromptOp() >> ChatOp()
    description: "简单的对话流程"
```

#### 2.3 多行表达式

Flow 表达式支持多行，前面的行用于设置上下文（如变量赋值），**最后一行必须是返回 BaseOp 的表达式**。

**规则：**
- 前面的行可以包含赋值语句，用于准备上下文。
- 最后一行必须是表达式（不能是赋值），且必须返回一个 `BaseOp` 实例。

**示例 1：变量赋值后返回**

```yaml
flow:
  multiline_flow:
    flow_content: |
      op = ContainerOp()
      op.ops.search = SearchOp()
      op.ops.find = FindOp()
      op
```

**示例 2：变量重新赋值**

```yaml
flow:
  reassign_flow:
    flow_content: |
      opx = Op1Op() >> Op2Op()
      opx = opx >> Op3Op()
      opx
```

**示例 3：复杂组合**

```yaml
flow:
  complex_flow:
    flow_content: |
      op1 = Op1Op()
      op1.ops.search = SearchOp()
      op1.ops.find = FindOp()
      (op1 | Op2Op()) >> Op3Op()
```

#### 2.4 属性赋值

可以为 Op 实例的属性赋值，特别是容器类 Op 的 `ops` 属性：

```yaml
flow:
  attribute_flow:
    flow_content: |
      op = ContainerOp()
      op.ops.search = SearchOp()
      op.ops.find = FindOp()
      op
```

#### 2.5 左移运算符（`<<`）

使用 `<<` 运算符可以批量设置容器 Op 的子操作：

```yaml
flow:
  left_shift_flow:
    flow_content: |
      op = ContainerOp()
      op << {"search": Op1Op(), "find": Op2Op()}
      (op | Op2Op()) >> (Op1Op() | Op3Op()) >> op
```

这等价于：
```python
op.ops.search = Op1Op()
op.ops.find = Op2Op()
```

---

### 三、完整配置示例

以下是一个包含多种 Flow 配置的完整示例：

```yaml
flow:
  # 简单的顺序流程
  demo_http_flow:
    flow_content: GenSystemPromptOp() >> ChatOp()
    description: "AI 对话助手"
    input_schema:
      query:
        type: string
        description: "用户查询"
        required: true

  # 流式输出流程
  demo_stream_http_flow:
    flow_content: GenSystemPromptOp() >> StreamChatOp()
    stream: true
    description: "流式 AI 对话助手"
    input_schema:
      query:
        type: string
        description: "用户查询"
        required: true

  # 简单的单 Op 流程
  demo_mcp_flow:
    flow_content: MockSearchOp()
    description: "搜索查询结果"
    input_schema:
      query:
        type: string
        description: "用户查询"
        required: true

  # 多行复杂流程
  complex_multiline_flow:
    flow_content: |
      container = ContainerOp()
      container.ops.search = SearchOp()
      container.ops.find = FindOp()
      (container | ProcessOp()) >> FormatOp()
    description: "复杂的多步骤流程"

  # 使用左移运算符的流程
  left_shift_flow:
    flow_content: |
      op = ContainerOp()
      op << {"search": SearchOp(), "find": FindOp()}
      op >> ProcessOp()
    description: "使用左移运算符设置子操作"
```

---

### 四、表达式解析规则

Flow 表达式由 `parse_flow_expression` 函数解析，遵循以下规则：

1. **Op 注册要求**
   - 表达式中使用的 Op 类必须已在 `C.registry_dict["op"]` 中注册。
   - 可以使用注册时的名称，或直接使用类名。

2. **多行处理**
   - 所有非空行会被处理。
   - 前面的行通过 `exec()` 执行，用于设置上下文。
   - 最后一行通过 `eval()` 求值，必须返回 `BaseOp` 实例。

3. **最后一行限制**
   - **必须是表达式**，不能是赋值语句。
   - **必须返回 BaseOp**，否则会抛出 `AssertionError`。

4. **执行环境**
   - 表达式在受限环境中执行，只包含已注册的 Op 类。
   - 不支持标准库函数，仅支持 Op 类的实例化和运算符操作。

---

### 五、常见模式与最佳实践

#### 5.1 简单顺序流程
适用于需要按步骤执行的场景：

```yaml
flow_content: Step1Op() >> Step2Op() >> Step3Op()
```

#### 5.2 并行处理
适用于可以同时执行多个独立任务的场景：

```yaml
flow_content: FetchDataOp() | ProcessDataOp() | ValidateDataOp()
```

#### 5.3 条件分支（通过容器 Op）
使用容器 Op 实现条件逻辑：

```yaml
flow_content: |
  container = ContainerOp()
  container.ops.branch1 = Branch1Op()
  container.ops.branch2 = Branch2Op()
  container
```

#### 5.4 组合模式
顺序和并行混合使用：

```yaml
flow_content: |
  PrepareOp() >> (ParallelOp1() | ParallelOp2()) >> MergeOp()
```

#### 5.5 流式输出
对于需要实时返回结果的场景，设置 `stream: true`：

```yaml
stream_flow:
  flow_content: GenSystemPromptOp() >> StreamChatOp()
  stream: true
```

---

### 六、调试技巧

1. **检查 Op 注册**
   - 确保所有使用的 Op 都已正确注册。
   - 检查 Op 类名是否正确（区分大小写）。

2. **验证表达式语法**
   - 最后一行必须是表达式，不能是赋值。
   - 确保括号匹配。

3. **测试简单表达式**
   - 先测试单 Op：`SingleOp()`
   - 再测试简单组合：`Op1() >> Op2()`
   - 逐步增加复杂度。

4. **查看错误信息**
   - `ValueError: flow content is empty` - 表达式为空
   - `AssertionError: Expression '...' did not evaluate to a BaseOp instance` - 最后一行未返回 BaseOp
   - `NameError` - Op 类未注册或名称错误

---

### 七、与 input_schema 的配合

`input_schema` 定义了 Flow 的输入接口，与 `flow_content` 配合使用。注意不同运行模式的要求：

- MCP 模式：`input_schema` 为**必填**，且需与真实入参严格一致，MCP 客户端会基于该定义进行参数校验与提示。
- HTTP/Stream 模式：`input_schema` 为**可选**，但建议填写以获得更好的入参校验与自动生成文档的体验。

```yaml
flow:
  search_flow:
    flow_content: SearchOp() >> FormatOp()
    description: "搜索并格式化结果"
    input_schema:
      query:
        type: string
        description: "搜索关键词"
        required: true
      limit:
        type: integer
        description: "结果数量限制"
        required: false
        default: 10
```

这样配置后，调用该 Flow 时需要提供符合 `input_schema` 的输入参数。

---

### 八、参考资源

- **测试用例**：`tests/test_expression_parser.py` 包含大量 Flow 表达式示例
- **解析函数**：`flowllm/core/utils/common_utils.py` 中的 `parse_flow_expression` 函数
- **Op 介绍**：参考 `op_introduction.md` 了解可用的 Op 类型

