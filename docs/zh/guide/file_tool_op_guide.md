# File Tool Op 介绍

File Tool Op 是 FlowLLM 框架提供的文件操作工具集，基于 `BaseAsyncToolOp` 实现，为 LLM 提供了丰富的文件系统操作能力。

## 功能概览

File Tool Op 包含 13 个操作，分为以下几类：

| 类别       | Op 名称             | 工具名称          | 主要功能                       |
|----------|-------------------|---------------|----------------------------|
| **文件读取** | `ReadFileOp`      | ReadFile      | 读取单个文件内容，支持指定行范围           |
|          | `ReadManyFilesOp` | ReadManyFiles | 批量读取匹配 glob 模式的文件          |
| **文件写入** | `WriteFileOp`     | WriteFile     | 写入文件内容，自动创建目录              |
| **文件编辑** | `EditOp`          | Edit          | 基础文本替换编辑                   |
|          | `SmartEditOp`     | SmartEdit     | 智能编辑，支持精确匹配、灵活匹配、正则匹配      |
| **文件搜索** | `GlobOp`          | FindFiles     | 按 glob 模式查找文件，支持 gitignore |
|          | `GrepOp`          | Grep          | 正则表达式文本搜索                  |
|          | `RipGrepOp`       | RipGrep       | 高级文本搜索（类似 ripgrep）         |
| **目录操作** | `LSOp`            | ListDirectory | 列出目录内容                     |
| **系统操作** | `ShellOp`         | ExecuteShell  | 执行 shell 命令，支持前台/后台执行      |
| **任务管理** | `TaskOp`          | Task          | 委托任务给专门的子代理                |
|          | `WriteTodosOp`    | WriteTodos    | 管理待办事项列表                   |
|          | `ExitPlanModeOp`  | ExitPlanMode  | 退出计划模式                     |

## 详细说明

### 文件读取类

#### ReadFileOp
- **功能**：读取单个文件内容
- **主要参数**：
  - `absolute_path` (必需): 文件绝对路径
  - `offset` (可选): 起始行号（从 0 开始）
  - `limit` (可选): 读取行数
- **特点**：支持大文件的分段读取

#### ReadManyFilesOp
- **功能**：批量读取多个文件
- **主要参数**：
  - `pattern` (必需): glob 匹配模式
  - `dir_path` (可选): 搜索目录
- **特点**：自动过滤 gitignore 文件，按修改时间排序

### 文件写入类

#### WriteFileOp
- **功能**：写入文件内容
- **主要参数**：
  - `file_path` (必需): 文件路径
  - `content` (必需): 文件内容
- **特点**：自动创建父目录，支持覆盖已存在文件

### 文件编辑类

#### EditOp
- **功能**：基础文本替换
- **主要参数**：
  - `file_path` (必需): 文件路径
  - `old_string` (必需): 要替换的文本
  - `new_string` (必需): 替换后的文本
  - `expected_replacements` (可选): 期望替换次数
- **特点**：精确匹配，支持创建新文件（old_string 为空）

#### SmartEditOp
- **功能**：智能文本替换
- **主要参数**：
  - `file_path` (必需): 文件路径
  - `old_string` (必需): 要替换的文本
  - `new_string` (必需): 替换后的文本
  - `match_type` (可选): 匹配类型（exact/flexible/regex）
- **特点**：支持三种匹配策略，灵活处理缩进差异

### 文件搜索类

#### GlobOp
- **功能**：按 glob 模式查找文件
- **主要参数**：
  - `pattern` (必需): glob 模式
  - `dir_path` (可选): 搜索目录
- **特点**：支持 gitignore 过滤，按修改时间排序

#### GrepOp
- **功能**：正则表达式文本搜索
- **主要参数**：
  - `pattern` (必需): 正则表达式
  - `path` (可选): 搜索路径
  - `glob` (可选): 文件过滤模式
  - `limit` (可选): 结果数量限制
- **特点**：支持多文件搜索，返回匹配行及上下文

#### RipGrepOp
- **功能**：高级文本搜索
- **主要参数**：
  - `pattern` (必需): 搜索模式
  - `path` (可选): 搜索路径
  - `glob` (可选): 文件过滤模式
- **特点**：类似 ripgrep 的高性能搜索

### 目录操作类

#### LSOp
- **功能**：列出目录内容
- **主要参数**：
  - `path` (必需): 目录路径
  - `ignore` (可选): 忽略的 glob 模式列表
- **特点**：返回文件和子目录名称列表

### 系统操作类

#### ShellOp
- **功能**：执行 shell 命令
- **主要参数**：
  - `command` (必需): shell 命令
  - `is_background` (必需): 是否后台执行
  - `description` (可选): 命令描述
  - `dir_path` (可选): 执行目录
- **特点**：支持前台/后台执行，返回输出和退出码

### 任务管理类

#### TaskOp
- **功能**：委托任务给子代理
- **主要参数**：
  - `description` (必需): 任务描述
  - `prompt` (必需): 任务提示
  - `subagent_type` (必需): 子代理类型
- **特点**：支持任务分解和委托

#### WriteTodosOp
- **功能**：管理待办事项
- **主要参数**：
  - `todos` (必需): 待办事项列表
- **特点**：跟踪和管理子任务

#### ExitPlanModeOp
- **功能**：退出计划模式
- **主要参数**：
  - `reason` (必需): 退出原因
- **特点**：用于控制流程执行模式

## 使用示例

所有 File Tool Op 都继承自 `BaseAsyncToolOp`，可以通过工具调用的方式使用：

```python
from flowllm.extensions.file_tool import ReadFileOp, WriteFileOp, EditOp

# 读取文件
read_op = ReadFileOp()
result = await read_op(absolute_path="/path/to/file.py", offset=0, limit=100)

# 写入文件
write_op = WriteFileOp()
result = await write_op(file_path="/path/to/new_file.py", content="print('Hello')")

# 编辑文件
edit_op = EditOp()
result = await edit_op(
    file_path="/path/to/file.py",
    old_string="old code",
    new_string="new code"
)
```

## 注意事项

1. 所有 Op 默认 `raise_exception=False`，失败时返回错误信息而非抛出异常
2. 文件路径支持 `~` 扩展，会自动解析为绝对路径
3. 搜索类 Op 会自动过滤 `.gitignore` 中的文件
4. 编辑类 Op 会验证替换次数，确保操作准确性
