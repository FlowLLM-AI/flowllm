# 上下文管理（Context Management）指南

## 一、背景

### 1.1 从提示工程到上下文工程

在 AI 发展的历程中，我们经历了两个重要的工程阶段：

- **提示工程（Prompt Engineering）**：2022年12月 ChatGPT 发布后兴起，专注于如何为聊天模型编写有效的指令和提示。

- **上下文工程（Context Engineering）**：2024年5月左右出现，与"智能体之年"概念同步。随着智能体应用的普及，如何管理不断增长的上下文成为新的挑战。

### 1.2 智能体带来的新问题

智能体的工作模式是：
- 大语言模型（LLM）绑定工具
- LLM 在循环中自主调用工具
- 每次工具调用后，结果被追加到消息历史中
- 消息历史不断累积，导致上下文爆炸式增长

**典型数据**：
- 一个典型任务可能需要 **50次工具调用**
- 生产环境中的智能体可能进行 **数百轮对话**
- 每次工具调用都会产生大量 token 占用

## 二、核心挑战

### 2.1 上下文爆炸

智能体在运行过程中，上下文会以特定方式不断增长：
- 工具调用结果不断累积
- 消息列表无限增长
- 上下文窗口被快速填满

### 2.2 上下文腐烂（Context Rot）

**核心问题**：随着上下文增长，模型性能会下降。

表现包括：
- 重复输出
- 推理速度变慢
- 输出质量下降

### 2.3 根本悖论

智能体面临一个矛盾：
- **需要**：大量上下文来支持工具调用和决策
- **问题**：上下文增长导致性能下降

这就是为什么需要"上下文工程"——在上下文窗口中填充**恰到好处的信息**，既满足决策需求，又避免性能退化。

## 三、解决方案

业界已经形成了五种主要的上下文管理策略：

### 3.1 上下文卸载（Context Offloading）

**核心思想**：并非所有上下文都需要存在于消息历史中，可以将信息卸载到外部存储，需要时再检索。

**实现方式**：
- **文件系统卸载**：将工具消息输出转储到文件系统
- 只向智能体返回最小必要信息（如文件路径）
- 完整内容保留在文件系统中，按需读取

**应用场景**：
- 网页搜索结果（占用大量 token）
- 大型工具输出
- 中间状态和计划

**优势**：
- 大幅减少上下文占用
- 信息不丢失，可随时检索
- 生产级智能体的标准做法

### 3.2 上下文缩减（Context Reduction）

上下文缩减分为两种方式：**压缩（Compaction）**和**摘要（Summarization）**。

#### 3.2.1 压缩（Compaction）

**原理**：将信息从完整格式转换为紧凑格式，剥离可以从外部状态重建的信息。

**示例**：
- 写入文件工具返回：`{path: "/file.txt", content: "很长的内容..."}`
- 压缩后：只保留 `{path: "/file.txt"}`
- 需要时通过路径重新读取文件

**特点**：
- ✅ **可逆**：信息未丢失，可随时恢复
- ✅ 大幅减少 token 占用
- ✅ 适合工具调用结果

**注意事项**：
- 压缩最旧的工具调用（如最旧的50%）
- 保留最新的工具调用完整细节，作为使用示例

**生产级实现示例：工具结果清除（Tool Result Clearing）**

工具结果清除是压缩的自动化实现方式，由服务端自动执行。这是生产级智能体系统的标准做法，Claude 3.5 等模型已内置支持。

**核心机制**：
- **自动触发**：当上下文超过配置阈值时，自动按时间顺序清除最旧的工具结果
- **占位符替换**：用占位符文本替换被清除的内容，让模型知道内容已被移除
- **选择性清除**：默认只清除工具结果，保留工具调用（参数），可选同时清除工具调用和结果
- **服务端处理**：在服务端自动执行，客户端保持完整历史记录，无需同步状态

**示例场景**：

假设一个智能体执行了多次网络搜索和文件操作：

```
[工具调用 1] web_search("AI最新进展")
  → 结果：5000 tokens 的搜索结果

[工具调用 2] write_file("research.txt", "很长的研究内容...")
  → 结果：3000 tokens 的文件内容

[工具调用 3] web_search("机器学习趋势")
  → 结果：4500 tokens 的搜索结果

[工具调用 4] read_file("research.txt")
  → 结果：3000 tokens 的文件内容

[工具调用 5] web_search("深度学习应用")
  → 结果：4800 tokens 的搜索结果
```

当上下文达到阈值（如 30K tokens）时，工具结果清除会自动：
1. 清除最旧的工具结果（工具调用 1 和 2 的结果）
2. 用占位符替换：`[工具结果已清除]`
3. 保留最近的工具调用（3、4、5）的完整结果
4. 保留所有工具调用的参数，模型仍知道执行了什么操作

**关键特性**：
- ✅ **智能保留**：保留最近 N 个工具使用/结果对，确保模型有最新的使用示例
- ✅ **缓存感知**：考虑与提示缓存的交互，优化成本效益
- ✅ **可配置排除**：可指定某些工具的结果永不清除，保护重要上下文
- ✅ **最小清除量**：确保清除操作值得缓存失效的成本

参考文档：[Claude Context Editing 官方文档](https://docs.claude.com/en/docs/build-with-claude/context-editing)

#### 3.2.2 摘要（Summarization）

**原理**：对上下文进行摘要或压缩，生成更短的版本。

**实现方式**：
- 对工具调用输出进行摘要
- 对完整消息历史进行摘要

**特点**：
- ❌ **不可逆**：信息可能丢失
- ✅ 进一步减少上下文长度

**与压缩的区别**：
- **压缩**：直接移除内容，用占位符替换或保留路径引用（可逆，通过检索恢复）
- **摘要**：压缩内容为更短版本（不可逆，信息可能丢失）

**最佳实践**：
- 摘要前先卸载关键部分到文件
- 使用完整版本进行摘要，而非压缩版本
- 保留最后几次工具调用的完整细节
- 识别"腐烂前阈值"（通常 128K-200K token）作为触发点

#### 3.2.3 压缩和摘要的选择策略

上下文缩减的两种方式各有特点：

| 方式 | 可逆性 | 适用场景 | 实现难度 |
|------|--------|----------|----------|
| **压缩（Compaction）** | ✅ 完全可逆 | 工具结果可从外部重建 | 中等（自动化实现：低） |
| **摘要（Summarization）** | ❌ 不可逆 | 需要进一步压缩时 | 高 |

**选择策略**：

1. **优先使用压缩**：可逆且安全，适合工具结果（包括工具结果清除等自动化实现）
2. **最后考虑摘要**：当压缩仍不够时，对保留内容进行摘要
3. **阈值管理**：
   - 硬性限制：如 100万 token
   - 腐烂前阈值：通常 128K-200K token
   - 接近阈值时触发缩减（优先压缩，必要时摘要）

**实际工作流示例**：

```
上下文增长 → 达到阈值（30K tokens）
  ↓
第一步：压缩工具结果（保留路径，移除内容，或使用工具结果清除）
  ↓
上下文仍接近阈值
  ↓
第二步：摘要保留的内容（对历史消息进行摘要）
```

### 3.3 上下文检索（Retrieving Context）

**核心思想**：按需检索已卸载的上下文信息。

**检索方式**：

1. **语义搜索**：
   - 使用向量索引
   - 基于语义相似度检索
   - 适合复杂查询

2. **文件系统搜索**：
   - 使用 `glob` 和 `grep` 等工具
   - 简单高效
   - 适合结构化文件

**应用场景**：
- 检索已卸载的研究计划
- 查找历史工具调用结果
- 恢复摘要前的完整上下文

**关键点**：
- 检索能力决定了卸载的安全性
- 稳定的检索使隔离变得安全
- 检索和卸载相互配合，实现高效管理

### 3.4 上下文隔离（Context Isolation）

**核心思想**：通过多智能体架构，将上下文拆分到不同的子智能体中。

#### 3.4.1 两种模式

**1. 通过通信（By Communicating）**

- 主智能体编写任务指令
- 发送给子智能体，子智能体上下文仅包含该指令
- 子智能体完成任务后返回结果
- 主智能体不关心子智能体的执行过程

**适用场景**：
- 任务有清晰简短的指令
- 只有最终输出重要
- 例如：在代码库中搜索特定片段

**优势**：
- 上下文小，开销低
- 简单直接

**2. 通过共享内存（By Sharing Memory）**

- 子智能体可以看到所有历史上下文
- 子智能体有自己的系统提示和动作空间
- 共享完整的工具使用历史

**适用场景**：
- 需要完整历史信息的复杂任务
- 最终输出依赖大量中间结果
- 例如：深度研究场景，需要大量搜索和笔记

**权衡**：
- ✅ 可以访问完整历史
- ❌ 每个子智能体需要更大的输入预填充
- ❌ 无法重用 KV 缓存，成本更高

#### 3.4.2 选择建议

- **简单任务**：使用通信模式
- **复杂任务**：使用共享内存模式
- **注意**：多智能体同步信息可能成为挑战，需要谨慎设计

### 3.5 缓存上下文（Caching Context）

**核心思想**：缓存重复使用的上下文，避免重复计算。

**应用**：
- 缓存工具定义
- 缓存常用查询结果
- 提高系统效率

**注意**：缓存与隔离、缩减之间存在权衡关系。

### 3.6 分层动作空间（Layered Action Space）

随着系统增长，工具本身也会占用大量上下文，导致"上下文混淆"（模型调用错误工具）。

**解决方案**：分层动作空间，将工具卸载到不同层级。

#### 三层架构

**1. 函数调用（Function Calling）**
- 经典模式，模式安全
- 固定数量的原子函数：读写文件、执行 shell、搜索、浏览器操作
- 缺点：太多工具会破坏缓存、引起混淆

**2. 沙盒工具（Sandbox Utilities）**
- 通过 shell 命令访问预安装工具
- 工具在虚拟机沙盒中运行
- 例如：格式转换器、语音识别、MCP CLI
- 优势：
  - 可添加新功能而不影响函数调用空间
  - 大输出可写入文件或分页
  - 可使用 Linux 工具（grep、cat、less）处理结果

**3. 包和 API（Packages and APIs）**
- 编写 Python 脚本调用预授权 API 或自定义包
- 适合需要大量计算但不需要将所有数据推送到上下文的任务
- 例如：分析股票价格数据、3D 建模、金融 API
- 优势：
  - 代码可组合，一步完成多件事
  - 只将摘要放回上下文

**统一接口**：
- 从模型角度看，三层都通过标准函数调用访问
- 接口简单、对缓存友好、函数间正交

## 四、方案之间的关系

五个维度（卸载、缩减、检索、隔离、缓存）并非独立，而是相互关联：

- **卸载 + 检索** → 使更高效的缩减成为可能
- **稳定的检索** → 使隔离变得安全
- **隔离** → 减慢上下文增长速度，降低缩减频率
- **隔离 + 缩减** → 影响缓存效率和输出质量

**核心原则**：上下文工程是一门在多个潜在冲突目标之间取得平衡的艺术与科学。

## 五、实践建议

### 5.1 避免过度工程化

**重要提醒**：避免过度工程化上下文（Avoid Context Over-Engineering）

**经验教训**：
- 最大的改进往往来自**简化**，而非添加更多技巧
- 移除不必要的技巧，更多信任模型
- 简化架构 → 更快、更稳定、更聪明

**核心理念**：
> 上下文工程的目标应该是让模型的工作变得更简单，而不是更难。

### 5.2 关键原则

1. **少构建，多理解**（Build Less and Understand More）
2. **优先使用可逆方案**（压缩 > 摘要）
3. **识别并监控阈值**（腐烂前阈值）
4. **选择合适的隔离模式**（通信 vs 共享内存）
5. **平衡多个目标**（性能、成本、质量）

### 5.3 实施步骤

1. **评估当前上下文使用情况**
   - 监控上下文长度
   - 识别性能下降点（腐烂前阈值）

2. **优先实施卸载**
   - 将大型工具输出卸载到文件系统
   - 建立检索机制

3. **实施压缩策略**
   - 设计紧凑格式
   - 设置压缩阈值

4. **考虑隔离**
   - 评估是否需要多智能体
   - 选择合适的通信模式

5. **持续优化**
   - 监控效果
   - 简化架构
   - 避免过度工程化

## 六、代码实现

### 6.1 上下文缩减（Context Reduction）

上下文缩减提供三种接口：压缩（Compaction）、摘要（Summary）和融合接口。

#### 6.1.1 压缩接口（Compaction）

**功能**：将工具调用结果从完整格式转换为紧凑格式，将可重建的信息卸载到外部存储。

**输入**：
```python
{
    "messages": List[Message],      # 完整的消息历史
    "compaction_config": {
        "compress_ratio": 0.5,      # 压缩比例：压缩最旧的 50% 工具调用
        "keep_recent": 3,           # 保留最近 N 个工具调用的完整结果
        "storage_path": "/tmp/context",  # 外部存储路径（文件系统或数据库）
        "exclude_tools": ["web_search"]  # 排除的工具列表（这些工具的结果不压缩）
    }
}
```

**输出**：
```python
{
    "messages": List[Message],      # 压缩后的消息历史（工具结果被替换为路径引用）
    "offloaded_data": {
        "files": [                  # 卸载到文件系统的数据
            {
                "path": "/tmp/context/tool_1_result.json",
                "tool_call_id": "call_123",
                "original_tokens": 5000,
                "compressed_tokens": 50
            }
        ],
        "db_records": [             # 卸载到数据库的数据（可选）
            {
                "record_id": "rec_456",
                "tool_call_id": "call_124",
                "original_tokens": 3000,
                "compressed_tokens": 30
            }
        ]
    },
    "statistics": {
        "original_tokens": 80000,
        "compressed_tokens": 40000,
        "saved_tokens": 40000,
        "compressed_tool_calls": 10,
        "kept_tool_calls": 3
    }
}
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `compress_ratio` | float (0-1) | 压缩比例，如 0.5 表示压缩最旧的 50% 工具调用 |
| `keep_recent` | int | 保留最近 N 个工具调用的完整结果，作为使用示例 |
| `storage_path` | string | 外部存储路径，可以是文件系统路径或数据库连接字符串 |
| `exclude_tools` | List[string] | 排除的工具名称列表，这些工具的结果不会被压缩 |

#### 6.1.2 摘要接口（Summary）

**功能**：对上下文进行摘要，在摘要前将关键部分卸载到文件系统。

**输入**：
```python
{
    "messages": List[Message],      # 完整的消息历史
    "summary_config": {
        "summary_ratio": 0.3,        # 摘要比例：摘要最旧的 30% 消息
        "keep_recent": 5,            # 保留最近 N 条消息的完整内容
        "offload_before_summary": True,  # 是否在摘要前卸载关键部分
        "offload_path": "/tmp/context/pre_summary",  # 摘要前卸载路径
        "dump_full_context": True    # 是否将整个摘要前的上下文转储为日志文件
    }
}
```

**输出**：
```python
{
    "messages": List[Message],      # 摘要后的消息历史
    "offloaded_data": {
        "key_parts": [              # 摘要前卸载的关键部分
            {
                "path": "/tmp/context/pre_summary/key_info_1.json",
                "content_type": "tool_results",
                "original_tokens": 10000
            }
        ],
        "full_context_dump": {      # 完整的摘要前上下文转储（如果启用）
            "path": "/tmp/context/pre_summary/full_context.log",
            "original_tokens": 50000
        }
    },
    "summary_info": {
        "summarized_messages": 15,
        "kept_messages": 5,
        "original_tokens": 50000,
        "summarized_tokens": 15000,
        "saved_tokens": 35000
    }
}
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `summary_ratio` | float (0-1) | 摘要比例，如 0.3 表示摘要最旧的 30% 消息 |
| `keep_recent` | int | 保留最近 N 条消息的完整内容 |
| `offload_before_summary` | bool | 是否在摘要前将关键部分卸载到文件 |
| `offload_path` | string | 摘要前卸载的存储路径 |
| `dump_full_context` | bool | 是否将整个摘要前的上下文转储为日志文件 |

#### 6.1.3 融合接口（Combined）

**功能**：优先使用压缩，提供 token 计数对比，达到阈值后使用摘要。

**输入**：
```python
{
    "messages": List[Message],      # 完整的消息历史
    "combined_config": {
        "compaction_threshold": 30000,  # 压缩触发阈值（tokens）
        "summary_threshold": 80000,     # 摘要触发阈值（tokens）
        "compaction_config": {...},     # 压缩配置
        "summary_config": {...}         # 摘要配置
    }
}
```

**输出**：
```python
{
    "messages": List[Message],      # 处理后的消息历史
    "applied_strategy": "compaction" | "summary" | "none",  # 应用的策略
    "token_comparison": {
        "original_tokens": 70000,
        "after_compaction_tokens": 35000,  # 压缩后的 tokens（如果应用）
        "after_summary_tokens": None,      # 摘要后的 tokens（如果应用）
        "saved_tokens": 35000
    },
    "offloaded_data": {...},        # 卸载的数据
    "statistics": {...}             # 统计信息
}
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `compaction_threshold` | int | 压缩触发阈值（tokens），超过此值触发压缩 |
| `summary_threshold` | int | 摘要触发阈值（tokens），压缩后仍超过此值则触发摘要 |
| `compaction_config` | object | 压缩配置，参考压缩接口参数 |
| `summary_config` | object | 摘要配置，参考摘要接口参数 |

**Token 计数接口**：

**输入**：
```python
{
    "messages": List[Message],      # 消息历史
    "reduction_config": {
        "compaction_config": {...},  # 压缩配置
        "summary_config": {...}      # 摘要配置
    }
}
```

**输出**：
```python
{
    "original_tokens": int,          # 原始 tokens
    "after_compaction_tokens": int,  # 压缩后的 tokens
    "after_summary_tokens": int,     # 摘要后的 tokens
    "compaction_savings": int,       # 压缩节省的 tokens
    "summary_savings": int,          # 摘要节省的 tokens
    "total_savings": int              # 总共节省的 tokens
}
```

### 6.2 上下文检索（Context Retrieving）

上下文检索提供两种方式：基础检索工具和定制化技能。

#### 6.2.1 基础检索工具（Agentic Retrieve）

**功能**：提供 glob、grep 等文件工具，支持按需检索已卸载的上下文。

**输入**：
```python
{
    "query": str,                   # 检索查询
    "retrieve_config": {
        "tools": ["glob", "grep", "cat", "find"],  # 可用的检索工具
        "search_paths": [           # 搜索路径
            "/tmp/context",
            "/tmp/context/pre_summary"
        ],
        "file_patterns": ["*.json", "*.log", "*.txt"]  # 文件模式
    }
}
```

**输出**：
```python
{
    "results": [
        {
            "file_path": "/tmp/context/tool_1_result.json",
            "matched_content": "...",  # 匹配的内容片段
            "relevance_score": 0.85,
            "tool_used": "grep"
        }
    ],
    "retrieved_context": str,      # 检索到的完整上下文
    "tools_used": ["grep", "cat"]   # 使用的工具列表
}
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `query` | string | 检索查询字符串 |
| `tools` | List[string] | 可用的检索工具列表，如 ["glob", "grep", "cat", "find"] |
| `search_paths` | List[string] | 搜索路径列表 |
| `file_patterns` | List[string] | 文件模式列表，如 ["*.json", "*.log", "*.txt"] |

#### 6.2.2 定制化技能（Skills）

**功能**：提供更高级的检索技能，拆分为三个独立接口：`meta_info`、`read_skill`、`read_detail_skill`。

##### A. 元信息查询（meta_info）

**输入**：
```python
{
    "target": str  # 目标文件或路径
}
```

**输出**：
```python
{
    "file_size": int,
    "created_time": str,
    "tool_call_id": str,
    "original_tokens": int
}
```

##### B. 概要读取（read_skill）

**输入**：
```python
{
    "target": str  # 目标文件或路径
}
```

**输出**：
```python
{
    "skill_summary": str,
    "key_points": List[str]
}
```

##### C. 详细读取（read_detail_skill）

**输入**：
```python
{
    "target": str  # 目标文件或路径
}
```

**输出**：
```python
{
    "full_content": str,
    "sections": List[dict]
}
```

参考文档：[Claude Context Editing 官方文档](https://docs.claude.com/en/docs/build-with-claude/context-editing)

## 七、总结

上下文管理是智能体系统的核心挑战。通过合理运用**卸载、缩减、检索、隔离、缓存**等策略，可以在满足智能体需求的同时，保持系统性能和稳定性。

**记住**：最好的解决方案往往是最简单的。理解问题本质，选择合适工具，避免过度工程化。

---
