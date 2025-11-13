# Gemini CLI 上下文管理机制

## 概述

Gemini CLI 通过多层机制管理过长的对话上下文，确保在 token 限制内保留关键信息。核心策略包括：**预判溢出 → 自动压缩 → 内容截断 → 历史过滤**。

## 核心流程

### 1. Token 限制检测

**位置**: `core/client.ts` → `sendMessageStream()`

**机制**:
- 使用 `tokenLimit(modelForLimitCheck)` 获取模型最大 token 数
  - `gemini-1.5-pro`: 2,097,152 tokens
  - `gemini-1.5-flash`: 1,048,576 tokens
- 计算剩余可用 token: `getLastPromptTokenCount()`
- **触发条件**: 预计请求 token > 剩余空间 × 95%
- **事件**: 触发 `ContextWindowWillOverflow` 事件，阻止发送

### 2. 自动压缩机制

**位置**: `services/chatCompressionService.ts` → `compress()`

**压缩阈值**:
- `DEFAULT_COMPRESSION_TOKEN_THRESHOLD = 0.2` (20%)
- 当当前 token 数 > 模型限制 × 0.2 时触发压缩

**压缩策略**:
- **保留比例**: `COMPRESSION_PRESERVE_THRESHOLD = 0.3` (保留最新 30%)
- **分段压缩**:
  1. `findCompressSplitPoint()` 计算压缩起点（保留最新 30%）
  2. 将旧消息 (`historyToCompress`) 提交给 LLM 生成摘要
  3. 将摘要 + 保留的新消息 (`historyToKeep`) 组合为新历史
  4. 使用 `getCompressionPrompt()` 指导模型生成结构化摘要:
     - `<overall_goal>`: 用户高层目标
     - `<key_knowledge>`: 关键事实
     - `<file_system_state>`: 文件系统状态
     - `<recent_actions>`: 最近的重要操作
     - `<current_plan>`: 当前执行计划

**压缩 Prompt** (`core/prompts.ts` → `getCompressionPrompt()`):

压缩时使用的系统指令要求模型：

1. 在私有 `<scratchpad>` 中思考整个历史
2. 生成结构化的 `<state_snapshot>` XML 对象
3. 必须保留所有关键细节、计划、错误和用户指令

完整 Prompt 内容：

```
You are the component that summarizes internal chat history into a given structure.

When the conversation history grows too large, you will be invoked to distill the entire history into a concise, structured XML snapshot. This snapshot is CRITICAL, as it will become the agent's *only* memory of the past. The agent will resume its work based solely on this snapshot. All crucial details, plans, errors, and user directives MUST be preserved.

First, you will think through the entire history in a private <scratchpad>. Review the user's overall goal, the agent's actions, tool outputs, file modifications, and any unresolved questions. Identify every piece of information that is essential for future actions.

After your reasoning is complete, generate the final <state_snapshot> XML object. Be incredibly dense with information. Omit any irrelevant conversational filler.

The structure MUST be as follows:

<state_snapshot>
    <overall_goal>
        <!-- A single, concise sentence describing the user's high-level objective. -->
        <!-- Example: "Refactor the authentication service to use a new JWT library." -->
    </overall_goal>

    <key_knowledge>
        <!-- Crucial facts, conventions, and constraints the agent must remember based on the conversation history and interaction with the user. Use bullet points. -->
        <!-- Example:
         - Build Command: `npm run build`
         - Testing: Tests are run with `npm test`. Test files must end in `.test.ts`.
         - API Endpoint: The primary API endpoint is `https://api.example.com/v2`.
        -->
    </key_knowledge>

    <file_system_state>
        <!-- List files that have been created, read, modified, or deleted. Note their status and critical learnings. -->
        <!-- Example:
         - CWD: `/home/user/project/src`
         - READ: `package.json` - Confirmed 'axios' is a dependency.
         - MODIFIED: `services/auth.ts` - Replaced 'jsonwebtoken' with 'jose'.
         - CREATED: `tests/new-feature.test.ts` - Initial test structure for the new feature.
        -->
    </file_system_state>

    <recent_actions>
        <!-- A summary of the last few significant agent actions and their outcomes. Focus on facts. -->
        <!-- Example:
         - Ran `grep 'old_function'` which returned 3 results in 2 files.
         - Ran `npm run test`, which failed due to a snapshot mismatch in `UserProfile.test.ts`.
         - Ran `ls -F static/` and discovered image assets are stored as `.webp`.
        -->
    </recent_actions>

    <current_plan>
        <!-- The agent's step-by-step plan. Mark completed steps. -->
        <!-- Example:
         1. [DONE] Identify all files using the deprecated 'UserAPI'.
         2. [IN PROGRESS] Refactor `src/components/UserProfile.tsx` to use the new 'ProfileAPI'.
         3. [TODO] Refactor the remaining files.
         4. [TODO] Update tests to reflect the API change.
        -->
    </current_plan>
</state_snapshot>
```

**压缩执行流程**:

1. 将 `historyToCompress` 作为用户消息发送给 LLM
2. 添加用户提示: `"First, reason in your scratchpad. Then, generate the <state_snapshot>."`
3. 使用 `getCompressionPrompt()` 作为系统指令
4. 将生成的摘要作为新的用户消息，添加模型确认回复，然后拼接 `historyToKeep`

**失败保护**:
- 若压缩后 token 数反而增加，放弃压缩，返回原始历史
- 设置 `hasFailedCompressionAttempt = true` 防止重复尝试

**执行时机**: `agents/executor.ts` → `executeTurn()` → `tryCompressChat()`

### 3. 历史记录过滤

**位置**: `core/geminiChat.ts` → `extractCuratedHistory()`

**机制**:
- 遍历历史记录，仅保留有效的用户和模型对话轮次
- 过滤无效内容:
  - 安全过滤导致的空输出
  - 空 `parts` 或无效 `content`
  - 仅包含 function response 的消息
- `getHistory(curated: boolean)` 支持返回"综合历史"或"精炼历史"

### 4. 工具输出截断

**位置**: `core/coreToolScheduler.ts` → `truncateAndSaveToFile()`

**配置**:
- `DEFAULT_TRUNCATE_TOOL_OUTPUT_THRESHOLD = 4,000,000` 字符
- `DEFAULT_TRUNCATE_TOOL_OUTPUT_LINES = 1000` 行

**截断策略**:
- 保留前 `truncateLines / 5` 行和后 `truncateLines - head` 行
- 中间插入 `... [CONTENT TRUNCATED] ...` 标记
- 完整内容写入临时文件，提示使用 `READ_FILE_TOOL_NAME` 读取

**工具输出摘要**: `tools/shell.ts` → `summarizeToolOutput()`
- 当输出超过 `maxOutputTokens` 时，调用 LLM 生成摘要
- 特别保留错误堆栈 (`<error></error>`) 和警告 (`<warning></warning>`)

### 5. 文件内容管理

**位置**: `utils/fileUtils.ts` → `processSingleFileContent()`

**限制**:
- `DEFAULT_MAX_LINES_TEXT_FILE = 2000` 行
- `MAX_LINE_LENGTH_TEXT_FILE = 2000` 字符/行
- 超长行截断并添加 `... [truncated]` 标记

**IDE 上下文限制**: `ide/ideContext.ts`
- `IDE_MAX_SELECTED_TEXT_LENGTH = 16384` 字符
- `IDE_MAX_OPEN_FILES`: 限制打开文件数量（按时间戳保留最新）

### 6. 记忆持久化

**位置**: `utils/memoryDiscovery.ts` → `loadServerHierarchicalMemory()`

**机制**:
- 从工作目录、信任根目录、扩展文件等发现 `GEMINI.md` 文件
- 通过 `MemoryTool` 将关键事实写入 `GEMINI.md`
- 支持层级记忆: 向上 (`findUpwardGeminiFiles`) 和向下 (`bfsFileSearch`) 搜索
- 支持 JIT 加载 (`loadJitSubdirectoryMemory`)，按需加载子目录上下文

**导入处理**: `utils/memoryImportProcessor.ts` → `processImports()`
- `flat` 模式: 拼接所有导入内容
- `tree` 模式: 构建嵌套结构
- 安全控制: 防止路径遍历、限制递归深度

### 7. 事件机制

**关键事件**:
- `PreCompress`: 压缩前触发，支持手动/自动两种触发方式
- `ContextWindowWillOverflow`: 上下文窗口即将溢出
- `ChatCompressed`: 聊天已压缩，包含压缩前后 token 数

**Hook 支持**: `hooks/hookRunner.ts`
- `BeforeAgent` 事件允许注入 `additionalContext`
- 可在压缩前生成关键信息摘要并注入

### 8. 路由策略优化

**位置**: `routing/strategies/classifierStrategy.ts`

**机制**:
- 滑动窗口: `HISTORY_SEARCH_WINDOW = 20` 条消息
- 过滤非核心消息: 排除 function call/response
- 最终上下文: 仅取最后 `HISTORY_TURNS_FOR_CONTEXT = 4` 条

### 9. 其他优化机制

**循环检测**: `services/loopDetectionService.ts`
- 滚动窗口: `MAX_HISTORY_LENGTH = 5000` 字符
- 滑动窗口分析: `CONTENT_CHUNK_SIZE = 50`
- 动态截断防止内存无限增长

**LRU 缓存**: `utils/LruCache.ts`
- 自动淘汰最久未使用的条目
- 用于管理历史操作结果缓存

**活动监控**: `telemetry/activity-monitor.ts`
- `maxEventBuffer = 100` 事件
- FIFO 缓冲管理

## 关键数据结构

```typescript
// 压缩状态枚举
enum CompressionStatus {
  /** 压缩成功 */
  COMPRESSED = 1,

  /** 压缩失败：压缩后 token 数反而增加 */
  COMPRESSION_FAILED_INFLATED_TOKEN_COUNT,

  /** 压缩失败：token 计数错误 */
  COMPRESSION_FAILED_TOKEN_COUNT_ERROR,

  /** 无需压缩，未执行任何操作 */
  NOOP,
}

// 压缩信息
interface ChatCompressionInfo {
  compressionStatus: CompressionStatus;
  originalTokenCount: number;
  newTokenCount: number;
}

// 压缩事件
interface ChatCompressionEvent {
  tokens_before: number;
  tokens_after: number;
}

// 历史记录
interface Content {
  role: 'user' | 'model';
  parts: Part[];
}

// 压缩后的状态快照结构（XML 格式）
interface StateSnapshot {
  overall_goal: string;        // 用户高层目标（单句描述）
  key_knowledge: string;        // 关键事实、约定和约束（要点列表）
  file_system_state: string;    // 文件系统状态（创建/读取/修改/删除的文件）
  recent_actions: string;      // 最近的重要操作摘要
  current_plan: string;         // 当前执行计划（步骤列表，标记完成状态）
}
```

**压缩后的状态快照示例**:

```xml

<state_snapshot>
    <overall_goal>
        Refactor the authentication service to use a new JWT library.
    </overall_goal>

    <key_knowledge>
        - Build Command: `npm run build`
        - Testing: Tests are run with `npm test`. Test files must end in `.test.ts`.
        - API Endpoint: The primary API endpoint is `https://api.example.com/v2`.
    </key_knowledge>

    <file_system_state>
        - CWD: `/home/user/project/src`
        - READ: `package.json` - Confirmed 'axios' is a dependency.
        - MODIFIED: `services/auth.ts` - Replaced 'jsonwebtoken' with 'jose'.
        - CREATED: `tests/new-feature.test.ts` - Initial test structure for the new feature.
    </file_system_state>

    <recent_actions>
        - Ran `grep 'old_function'` which returned 3 results in 2 files.
        - Ran `npm run test`, which failed due to a snapshot mismatch in `UserProfile.test.ts`.
        - Ran `ls -F static/` and discovered image assets are stored as `.webp`.
    </recent_actions>

    <current_plan>
        1. [DONE] Identify all files using the deprecated 'UserAPI'.
        2. [IN PROGRESS] Refactor `src/components/UserProfile.tsx` to use the new 'ProfileAPI'.
        3. [TODO] Refactor the remaining files.
        4. [TODO] Update tests to reflect the API change.
    </current_plan>
</state_snapshot>
```

## 配置参数总结

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `COMPRESSION_TOKEN_THRESHOLD` | 0.2 | 压缩触发阈值（模型限制的20%） |
| `COMPRESSION_PRESERVE_THRESHOLD` | 0.3 | 保留最新消息比例（30%） |
| `TRUNCATE_TOOL_OUTPUT_THRESHOLD` | 4,000,000 | 工具输出截断阈值（字符） |
| `TRUNCATE_TOOL_OUTPUT_LINES` | 1000 | 工具输出最大行数 |
| `MAX_LINES_TEXT_FILE` | 2000 | 文本文件最大行数 |
| `MAX_LINE_LENGTH_TEXT_FILE` | 2000 | 单行最大长度 |
| `IDE_MAX_SELECTED_TEXT_LENGTH` | 16384 | IDE 选中文本最大长度 |
| `HISTORY_SEARCH_WINDOW` | 20 | 路由策略历史窗口大小 |
| `HISTORY_TURNS_FOR_CONTEXT` | 4 | 路由策略最终上下文条数 |

## 执行流程总结

```
每轮执行 (executeTurn)
  ↓
检测 token 限制 (sendMessageStream)
  ↓
[超限?] → 触发 ContextWindowWillOverflow 事件
  ↓
尝试压缩 (tryCompressChat)
  ↓
[超过阈值?] → 调用 ChatCompressionService.compress()
  ├─ 计算压缩起点 (保留最新30%)
  ├─ 生成摘要 (LLM)
  ├─ 组合新历史 (摘要 + 保留消息)
  └─ [压缩后token增加?] → 放弃压缩
  ↓
过滤历史 (extractCuratedHistory)
  ├─ 移除无效消息
  └─ 返回精炼历史
  ↓
处理工具输出
  ├─ [超长?] → truncateAndSaveToFile()
  └─ [启用摘要?] → summarizeToolOutput()
  ↓
发送请求
```

## 设计原则

1. **渐进式压缩**: 先尝试压缩，失败则回退
2. **保留关键信息**: 优先保留最新消息和关键代码变更
3. **多级防护**: Token 检测 → 压缩 → 截断 → 过滤
4. **可观测性**: 通过事件和遥测记录压缩效果
5. **持久化**: 关键信息写入 GEMINI.md，避免重复传递

