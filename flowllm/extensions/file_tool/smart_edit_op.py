"""Smart edit operation module.

This module provides a tool operation for intelligently editing files by replacing text.
It supports exact matching, flexible matching (ignoring indentation), and regex-based matching.
"""

from pathlib import Path

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall
from ..utils import (
    calculate_exact_replacement,
    calculate_flexible_replacement,
    calculate_regex_replacement,
)


@C.register_op()
class SmartEditOp(BaseAsyncToolOp):
    """Smart edit operation.

    This operation intelligently replaces text within a file using multiple strategies:
    exact matching, flexible matching (ignoring indentation), and regex-based matching.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "SmartEdit",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "file_path": {
                    "type": "string",
                    "description": self.get_prompt("file_path"),
                    "required": True,
                },
                "old_string": {
                    "type": "string",
                    "description": self.get_prompt("old_string"),
                    "required": True,
                },
                "new_string": {
                    "type": "string",
                    "description": self.get_prompt("new_string"),
                    "required": True,
                },
                "instruction": {
                    "type": "string",
                    "description": self.get_prompt("instruction"),
                    "required": True,
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the smart edit operation."""
        file_path: str = self.input_dict.get("file_path", "").strip()
        old_string: str = self.input_dict.get("old_string", "")
        new_string: str = self.input_dict.get("new_string", "")
        instruction: str = self.input_dict.get("instruction", "").strip()

        if not file_path:
            raise ValueError("The 'file_path' parameter cannot be empty.")

        if not instruction:
            raise ValueError("The 'instruction' parameter cannot be empty.")

        file_path_obj = Path(file_path).expanduser().resolve()
        file_exists = file_path_obj.exists() and file_path_obj.is_file()

        # Handle new file creation
        if not old_string and not file_exists:
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            file_path_obj.write_text(new_string, encoding="utf-8")
            self.set_output(f"Created new file: {file_path_obj}")
            return

        if not file_exists:
            raise FileNotFoundError(
                f"File not found: {file_path_obj}. Use an empty old_string to create a new file.",
            )

        if not old_string and file_exists:
            raise ValueError(
                f"Failed to edit. Attempted to create a file that already exists: {file_path_obj}",
            )

        # Read current content
        current_content = file_path_obj.read_text(encoding="utf-8")
        original_line_ending = "\r\n" if "\r\n" in current_content else "\n"
        current_content = current_content.replace("\r\n", "\n")

        # Try replacement strategies
        result = calculate_exact_replacement(current_content, old_string, new_string)
        if not result:
            result = calculate_flexible_replacement(current_content, old_string, new_string)
        if not result:
            result = calculate_regex_replacement(current_content, old_string, new_string)

        if not result:
            raise ValueError(
                f"Failed to edit, could not find the string to replace. "
                f"0 occurrences found for old_string in {file_path_obj}. "
                f"Ensure you're not escaping content incorrectly and check whitespace, indentation, and context.",
            )

        new_content, occurrences = result

        if occurrences == 0:
            raise ValueError(
                f"Failed to edit, 0 occurrences found for old_string in {file_path_obj}.",
            )

        if old_string == new_string:
            raise ValueError(
                f"No changes to apply. The old_string and new_string are identical in {file_path_obj}.",
            )

        # Restore original line endings
        if original_line_ending == "\r\n":
            new_content = new_content.replace("\n", "\r\n")

        # Write new content
        file_path_obj.write_text(new_content, encoding="utf-8")

        if occurrences == 1:
            result_msg = f"Successfully modified file: {file_path_obj} (1 replacement)."
        else:
            result_msg = f"Successfully modified file: {file_path_obj} ({occurrences} replacements)."

        self.set_output(result_msg)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        file_path: str = self.input_dict.get("file_path", "").strip()
        error_msg = f'Failed to edit file "{file_path}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
