"""File tool package for FlowLLM framework.

This package provides file-related operations that can be used in LLM-powered flows.
It includes ready-to-use operations for:

- EditOp: File editing operation for replacing text within files
- ExitPlanModeOp: Exit plan mode operation
- GlobOp: File search operation for finding files matching glob patterns
- GrepOp: Text search operation for finding patterns in files
- LSOp: List directory contents operation
- ReadFileOp: Read single file operation
- ReadManyFilesOp: Read multiple files operation matching glob patterns
- RipGrepOp: Advanced text search operation using ripgrep-like functionality
- ShellOp: Shell command execution operation
- SmartEditOp: Smart file editing operation with context awareness
- TaskOp: Task management operation
- WriteFileOp: Write file operation
- WriteTodosOp: To-do list management operation for tracking subtasks
"""

from .edit_op import EditOp
from .exit_plan_mode_op import ExitPlanModeOp
from .glob_op import GlobOp
from .grep_op import GrepOp
from .ls_op import LSOp
from .read_file_op import ReadFileOp
from .read_many_files_op import ReadManyFilesOp
from .rip_grep_op import RipGrepOp
from .shell_op import ShellOp
from .smart_edit_op import SmartEditOp
from .task_op import TaskOp
from .write_file_op import WriteFileOp
from .write_todos_op import WriteTodosOp

__all__ = [
    "EditOp",
    "ExitPlanModeOp",
    "GlobOp",
    "GrepOp",
    "LSOp",
    "ReadFileOp",
    "ReadManyFilesOp",
    "RipGrepOp",
    "ShellOp",
    "SmartEditOp",
    "TaskOp",
    "WriteFileOp",
    "WriteTodosOp",
]
