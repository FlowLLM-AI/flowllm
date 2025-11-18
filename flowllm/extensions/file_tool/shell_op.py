"""Shell command execution operation module.

This module provides a tool operation for executing shell commands.
It supports foreground and background execution, with optional directory
and description parameters.
"""

import asyncio
from pathlib import Path
from typing import Optional

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class ShellOp(BaseAsyncToolOp):
    """Shell command execution operation.

    This operation executes shell commands and returns their output,
    error messages, exit codes, and other execution details.
    Supports both foreground and background execution.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "ExecuteShell",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "command": {
                    "type": "string",
                    "description": self.get_prompt("command"),
                    "required": True,
                },
                "is_background": {
                    "type": "boolean",
                    "description": self.get_prompt("is_background"),
                    "required": True,
                },
                "description": {
                    "type": "string",
                    "description": self.get_prompt("description"),
                    "required": False,
                },
                "directory": {
                    "type": "string",
                    "description": self.get_prompt("directory"),
                    "required": False,
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the shell command operation."""
        command: str = self.input_dict.get("command", "").strip()
        is_background: bool = self.input_dict.get("is_background", False)
        description: Optional[str] = self.input_dict.get("description")
        directory: Optional[str] = self.input_dict.get("directory")

        # Validate command
        if not command:
            raise ValueError("The 'command' parameter cannot be empty.")

        # Determine working directory
        if directory:
            cwd = Path(directory).expanduser().resolve()
            if not cwd.exists():
                raise FileNotFoundError(f"Directory does not exist: {cwd}")
            if not cwd.is_dir():
                raise ValueError(f"Path is not a directory: {cwd}")
        else:
            cwd = Path.cwd()

        # Prepare command for execution
        if is_background:
            # For background execution, add & at the end if not present
            if not command.rstrip().endswith("&"):
                command = command.rstrip() + " &"

        # Execute command
        if is_background:
            # Background execution: start process and return immediately
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
            )
            # Don't wait for background processes
            pid = process.pid
            result_message = f"Command started in background (PID: {pid})"
            if description:
                result_message += f": {description}"
            result_message += f"\nCommand: {command}\nDirectory: {cwd}"
            self.set_output(result_message)
        else:
            # Foreground execution: wait for completion
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
            )

            stdout, stderr = await process.communicate()

            # Decode output
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            error_output = stderr.decode("utf-8", errors="replace") if stderr else ""

            # Build result message
            result_parts = [
                f"Command: {command}",
                f"Directory: {directory or '(current)'}",
                f"Output: {output if output else '(empty)'}",
                f"Error: {error_output if error_output else '(none)'}",
                f"Exit Code: {process.returncode if process.returncode is not None else '(none)'}",
            ]

            if description:
                result_parts.insert(1, f"Description: {description}")

            result_message = "\n".join(result_parts)
            self.set_output(result_message)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        command: str = self.input_dict.get("command", "").strip()
        error_msg = f'Failed to execute shell command "{command}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
