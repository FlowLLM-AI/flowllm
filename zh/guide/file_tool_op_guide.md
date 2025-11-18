# File Tool Op 介绍

File Tool Op 是 FlowLLM 框架提供的文件操作工具集，基于 `BaseAsyncToolOp` 实现，为 LLM 提供了丰富的文件系统操作能力。

## 功能概览

File Tool Op 包含 13 个操作，详细信息如下：

| 类别       | Op 名称             | 工具名称          | 主要参数                                                                 | 特点                                       |
|----------|-------------------|---------------|----------------------------------------------------------------------|------------------------------------------|
| **文件读取** | `ReadFileOp`      | ReadFile      | `absolute_path`(必需), `offset`(可选), `limit`(可选)                        | 支持大文件的分段读取                                |
|          | `ReadManyFilesOp` | ReadManyFiles | `pattern`(必需), `dir_path`(可选)                                      | 自动过滤 gitignore 文件，按修改时间排序                |
| **文件写入** | `WriteFileOp`     | WriteFile     | `file_path`(必需), `content`(必需)                                      | 自动创建父目录，支持覆盖已存在文件                          |
| **文件编辑** | `EditOp`          | Edit          | `file_path`(必需), `old_string`(必需), `new_string`(必需), `expected_replacements`(可选) | 精确匹配，支持创建新文件（old_string 为空）                |
|          | `SmartEditOp`     | SmartEdit     | `file_path`(必需), `old_string`(必需), `new_string`(必需), `match_type`(可选) | 支持三种匹配策略（exact/flexible/regex），灵活处理缩进差异 |
| **文件搜索** | `GlobOp`          | FindFiles     | `pattern`(必需), `dir_path`(可选)                                      | 支持 gitignore 过滤，按修改时间排序                    |
|          | `GrepOp`          | Grep          | `pattern`(必需), `path`(可选), `glob`(可选), `limit`(可选)                  | 支持多文件搜索，返回匹配行及上下文                          |
|          | `RipGrepOp`       | RipGrep       | `pattern`(必需), `path`(可选), `glob`(可选)                              | 类似 ripgrep 的高性能搜索                            |
| **目录操作** | `LSOp`            | ListDirectory | `path`(必需), `ignore`(可选)                                           | 返回文件和子目录名称列表                               |
| **系统操作** | `ShellOp`         | ExecuteShell  | `command`(必需), `is_background`(必需), `description`(可选), `dir_path`(可选) | 支持前台/后台执行，返回输出和退出码                        |
| **任务管理** | `TaskOp`          | Task          | `description`(必需), `prompt`(必需), `subagent_type`(必需)                  | 支持任务分解和委托                                  |
|          | `WriteTodosOp`    | WriteTodos    | `todos`(必需)                                                         | 跟踪和管理子任务                                   |
|          | `ExitPlanModeOp`  | ExitPlanMode  | `reason`(必需)                                                        | 用于控制流程执行模式                                 |

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
