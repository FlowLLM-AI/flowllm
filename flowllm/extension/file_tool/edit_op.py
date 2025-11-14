"""File edit operation module.

This module provides a tool operation for editing files by replacing text.
It supports creating new files, editing existing files, and replacing multiple occurrences.
"""

from pathlib import Path
from typing import Optional

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class EditOp(BaseAsyncToolOp):
    """File edit operation.

    This operation replaces text within a file. By default, replaces a single
    occurrence, but can replace multiple occurrences when expected_replacements
    is specified. Supports creating new files when old_string is empty.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "Edit",
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
                "expected_replacements": {
                    "type": "number",
                    "description": self.get_prompt("expected_replacements"),
                    "required": False,
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the file edit operation."""
        file_path: str = self.input_dict.get("file_path", "").strip()
        old_string: str = self.input_dict.get("old_string", "")
        new_string: str = self.input_dict.get("new_string", "")
        expected_replacements: Optional[int] = self.input_dict.get("expected_replacements")

        # Validate inputs
        if not file_path:
            raise ValueError("The 'file_path' parameter cannot be empty.")

        if expected_replacements is None:
            expected_replacements = 1

        if expected_replacements < 1:
            raise ValueError("The 'expected_replacements' parameter must be at least 1.")

        # Resolve file path
        file_path_obj = Path(file_path).expanduser().resolve()

        # Check if file exists
        file_exists = file_path_obj.exists() and file_path_obj.is_file()

        # Handle new file creation
        if not old_string and not file_exists:
            # Create new file
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            file_path_obj.write_text(new_string, encoding="utf-8")
            self.set_output(f"Created new file: {file_path_obj}")
            return

        # File must exist for editing
        if not file_exists:
            raise FileNotFoundError(
                f"File not found: {file_path_obj}. Use an empty old_string to create a new file.",
            )

        # Cannot create file that already exists
        if not old_string and file_exists:
            raise ValueError(
                f"Failed to edit. Attempted to create a file that already exists: {file_path_obj}",
            )

        # Read current content
        current_content = file_path_obj.read_text(encoding="utf-8")
        current_content = current_content.replace("\r\n", "\n")

        # Count occurrences
        occurrences = current_content.count(old_string)

        # Validate occurrences
        if occurrences == 0:
            raise ValueError(
                f"Failed to edit, could not find the string to replace. "
                f"0 occurrences found for old_string in {file_path_obj}.",
            )

        if occurrences != expected_replacements:
            occurrence_term = "occurrence" if expected_replacements == 1 else "occurrences"
            raise ValueError(
                f"Failed to edit, expected {expected_replacements} {occurrence_term} "
                f"but found {occurrences} for old_string in {file_path_obj}.",
            )

        # Check if old_string and new_string are identical
        if old_string == new_string:
            raise ValueError(
                f"No changes to apply. The old_string and new_string are identical in {file_path_obj}.",
            )

        # Perform replacement
        new_content = current_content.replace(old_string, new_string, occurrences)

        # Check if content actually changed
        if current_content == new_content:
            raise ValueError(
                f"No changes to apply. The new content is identical to the current content in {file_path_obj}.",
            )

        # Write new content
        file_path_obj.write_text(new_content, encoding="utf-8")

        # Set output
        result_msg = f"Successfully modified file: {file_path_obj} ({occurrences} replacements)."
        self.set_output(result_msg)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        file_path: str = self.input_dict.get("file_path", "").strip()
        error_msg = f'Failed to edit file "{file_path}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
