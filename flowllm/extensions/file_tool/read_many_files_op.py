"""Read many files operation module.

This module provides a tool operation for reading content from multiple files
specified by glob patterns. It concatenates the content with separators.
"""

import fnmatch
from pathlib import Path
from typing import List, Optional, Set

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall

DEFAULT_OUTPUT_SEPARATOR_FORMAT = "--- {filePath} ---"
DEFAULT_OUTPUT_TERMINATOR = "\n--- End of content ---"


@C.register_op()
class ReadManyFilesOp(BaseAsyncToolOp):
    """Read many files operation.

    This operation reads content from multiple files matching glob patterns
    and concatenates them with separators.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "ReadManyFiles",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": self.get_prompt("paths"),
                    "required": True,
                },
                "include": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": self.get_prompt("include"),
                    "required": False,
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": self.get_prompt("exclude"),
                    "required": False,
                },
                "dir_path": {
                    "type": "string",
                    "description": self.get_prompt("dir_path"),
                    "required": False,
                },
            },
        }

        return ToolCall(**tool_params)

    def _glob_match(
        self,
        root_dir: Path,
        pattern: str,
        case_sensitive: bool = False,
    ) -> List[Path]:
        """Match files using glob pattern."""
        matching_files: List[Path] = []

        # Check if pattern is an exact file path
        full_path = root_dir / pattern
        if full_path.exists() and full_path.is_file():
            matching_files.append(full_path)
            return matching_files

        # Handle ** pattern (recursive match)
        if "**" in pattern:
            parts = pattern.split("**", 1)
            prefix = parts[0].rstrip("/")
            suffix = parts[1] if len(parts) > 1 else ""

            for path in root_dir.rglob("*"):
                if not path.is_file():
                    continue

                rel_path = path.relative_to(root_dir)
                rel_str = str(rel_path).replace("\\", "/")

                if self._matches_glob_pattern(rel_str, prefix, suffix, case_sensitive):
                    matching_files.append(path)
        else:
            pattern_normalized = pattern.replace("\\", "/")
            for path in root_dir.rglob("*"):
                if not path.is_file():
                    continue

                rel_path = path.relative_to(root_dir)
                rel_str = str(rel_path).replace("\\", "/")

                if case_sensitive:
                    if fnmatch.fnmatch(rel_str, pattern_normalized):
                        matching_files.append(path)
                else:
                    if fnmatch.fnmatch(rel_str.lower(), pattern_normalized.lower()):
                        matching_files.append(path)

        return matching_files

    @staticmethod
    def _matches_glob_pattern(
        path_str: str,
        prefix: str,
        suffix: str,
        case_sensitive: bool,
    ) -> bool:
        """Check if a path matches a glob pattern with **."""
        if not case_sensitive:
            path_str = path_str.lower()
            prefix = prefix.lower()
            suffix = suffix.lower()

        if prefix and not path_str.startswith(prefix):
            return False

        if suffix and not fnmatch.fnmatch(path_str, f"*{suffix}"):
            return False

        return True

    def _should_exclude(self, file_path: Path, exclude_patterns: List[str], search_dir: Path) -> bool:
        """Check if a file should be excluded based on patterns."""
        if not exclude_patterns:
            return False

        rel_path = file_path.relative_to(search_dir)
        rel_str = str(rel_path).replace("\\", "/")

        for pattern in exclude_patterns:
            if "**" in pattern:
                parts = pattern.split("**", 1)
                prefix = parts[0].rstrip("/")
                suffix = parts[1] if len(parts) > 1 else ""
                if self._matches_glob_pattern(rel_str, prefix, suffix, False):
                    return True
            else:
                if fnmatch.fnmatch(rel_str.lower(), pattern.lower()):
                    return True

        return False

    async def async_execute(self):
        """Execute the read many files operation."""
        paths: List[str] = self.input_dict.get("paths", [])
        include: List[str] = self.input_dict.get("include", [])
        exclude: List[str] = self.input_dict.get("exclude", [])
        dir_path: Optional[str] = self.input_dict.get("dir_path")

        if not paths:
            raise ValueError("The 'paths' parameter cannot be empty.")

        # Determine search directory
        if dir_path:
            search_dir = Path(dir_path).expanduser().resolve()
            if not search_dir.exists():
                raise FileNotFoundError(f"Search path does not exist: {search_dir}")
            if not search_dir.is_dir():
                raise ValueError(f"Search path is not a directory: {search_dir}")
        else:
            search_dir = Path.cwd()

        # Collect all patterns
        all_patterns = paths + include
        all_files: Set[Path] = set()

        # Find matching files
        for pattern in all_patterns:
            matching_files = self._glob_match(search_dir, pattern, case_sensitive=False)
            for file_path in matching_files:
                if not self._should_exclude(file_path, exclude, search_dir):
                    all_files.add(file_path)

        if not all_files:
            self.set_output("No files found matching the specified patterns.")
            return

        # Sort files alphabetically
        sorted_files = sorted(all_files)

        # Read and concatenate file contents
        content_parts: List[str] = []
        skipped_files: List[tuple] = []

        for file_path in sorted_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                separator = DEFAULT_OUTPUT_SEPARATOR_FORMAT.replace(
                    "{filePath}",
                    str(file_path),
                )
                content_parts.append(f"{separator}\n\n{content}\n\n")
            except Exception as e:
                skipped_files.append((str(file_path), str(e)))

        if content_parts:
            content_parts.append(DEFAULT_OUTPUT_TERMINATOR)
            result = "".join(content_parts)
        else:
            result = "No files could be read successfully."

        # Add summary if there are skipped files
        if skipped_files:
            result += f"\n\nSkipped {len(skipped_files)} file(s):\n"
            for file_path, reason in skipped_files[:5]:
                result += f"- {file_path} (Reason: {reason})\n"
            if len(skipped_files) > 5:
                result += f"- ...and {len(skipped_files) - 5} more.\n"

        self.set_output(result)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        paths: List[str] = self.input_dict.get("paths", [])
        error_msg = f"Failed to read files matching patterns {paths}"
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
