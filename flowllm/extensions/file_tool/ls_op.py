"""List directory operation module.

This module provides a tool operation for listing files and subdirectories
in a specified directory path.
"""

import fnmatch
from pathlib import Path
from typing import List, Optional

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class LSOp(BaseAsyncToolOp):
    """List directory operation.

    This operation lists the names of files and subdirectories directly
    within a specified directory path. Can optionally ignore entries
    matching provided glob patterns.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "ListDirectory",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "path": {
                    "type": "string",
                    "description": self.get_prompt("path"),
                    "required": True,
                },
                "ignore": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": self.get_prompt("ignore"),
                    "required": False,
                },
            },
        }

        return ToolCall(**tool_params)

    def _should_ignore(self, name: str, patterns: Optional[List[str]]) -> bool:
        """Check if a filename matches any of the ignore patterns.

        Args:
            name: Filename to check.
            patterns: Array of glob patterns to check against.

        Returns:
            True if the filename should be ignored, False otherwise.
        """
        if not patterns:
            return False

        for pattern in patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    async def async_execute(self):
        """Execute the list directory operation."""
        path_str: str = self.input_dict.get("path", "").strip()
        ignore: Optional[List[str]] = self.input_dict.get("ignore")

        if not path_str:
            raise ValueError("The 'path' parameter cannot be empty.")

        dir_path = Path(path_str).expanduser().resolve()

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {dir_path}")

        entries = []
        for item in dir_path.iterdir():
            if self._should_ignore(item.name, ignore):
                continue

            try:
                stat = item.stat()
                is_dir = item.is_dir()
                entries.append(
                    {
                        "name": item.name,
                        "path": str(item.resolve()),
                        "isDirectory": is_dir,
                        "size": 0 if is_dir else stat.st_size,
                        "modifiedTime": stat.st_mtime,
                    },
                )
            except OSError:
                # Skip files that can't be accessed
                continue

        # Sort entries (directories first, then alphabetically)
        entries.sort(key=lambda x: (not x["isDirectory"], x["name"]))

        if not entries:
            self.set_output(f"Directory {dir_path} is empty.")
            return

        # Format output
        directory_content = "\n".join(
            f'[DIR] {entry["name"]}' if entry["isDirectory"] else entry["name"] for entry in entries
        )

        result_message = f"Directory listing for {dir_path}:\n{directory_content}"
        self.set_output(result_message)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        path_str: str = self.input_dict.get("path", "").strip()
        error_msg = f'Failed to list directory "{path_str}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
