"""Glob file search operation module.

This module provides a tool operation for finding files matching glob patterns.
It enables efficient file discovery based on name or path structure, especially
in large codebases. Files are sorted by modification time (newest first).
"""

import fnmatch
import time
from pathlib import Path
from typing import List, Optional

from loguru import logger
from pathspec import PathSpec
from pathspec.patterns.gitwildmatch import GitIgnorePattern

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class GlobOp(BaseAsyncToolOp):
    """Glob file search operation.

    This operation efficiently finds files matching specific glob patterns,
    returning absolute paths sorted by modification time (newest first).
    Supports gitignore patterns for filtering files.
    """

    file_path = __file__

    def __init__(self, gitignore_patterns: List[str] = None, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)
        self.gitignore_patterns = gitignore_patterns

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "FindFiles",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "pattern": {
                    "type": "string",
                    "description": self.get_prompt("pattern"),
                    "required": True,
                },
                "dir_path": {
                    "type": "string",
                    "description": self.get_prompt("dir_path"),
                    "required": False,
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": self.get_prompt("case_sensitive"),
                    "required": False,
                },
            },
        }

        return ToolCall(**tool_params)

    def _should_ignore_file(
        self,
        file_path: Path,
        root_dir: Path,
    ) -> bool:
        """Check if a file should be ignored based on ignore patterns.

        Args:
            file_path: Path to the file to check.
            root_dir: Root directory for resolving relative paths.

        Returns:
            True if the file should be ignored, False otherwise.
        """
        if not self.gitignore_patterns:
            return False

        ignore_spec = PathSpec.from_lines(GitIgnorePattern, self.gitignore_patterns)

        # Get relative path from root_dir
        relative_path = file_path.relative_to(root_dir)

        # Check if file matches ignore patterns
        return ignore_spec.match_file(str(relative_path))

    async def async_execute(self):
        """Execute the glob search operation."""
        pattern: str = self.input_dict.get("pattern", "").strip()
        dir_path: Optional[str] = self.input_dict.get("dir_path")
        case_sensitive: bool = self.input_dict.get("case_sensitive", False)

        # Validate pattern
        if not pattern:
            error_msg = "The 'pattern' parameter cannot be empty."
            logger.error(f"{self.name}: {error_msg}")
            self.set_output(error_msg)
            return

        # Determine search directory
        if dir_path:
            search_dir = Path(dir_path).expanduser().resolve()
            if not search_dir.exists():
                error_msg = f"Search path does not exist: {search_dir}"
                logger.error(f"{self.name}: {error_msg}")
                self.set_output(error_msg)
                return
            if not search_dir.is_dir():
                error_msg = f"Search path is not a directory: {search_dir}"
                logger.error(f"{self.name}: {error_msg}")
                self.set_output(error_msg)
                return
        else:
            search_dir = Path.cwd()

        # Collect matching files
        all_entries: List[Path] = []
        ignored_count = 0

        # Check if pattern is an exact file path
        full_path = search_dir / pattern
        if full_path.exists() and full_path.is_file():
            # Use exact match
            if not self._should_ignore_file(
                full_path,
                search_dir,
            ):
                all_entries.append(full_path)
        else:
            # Use glob pattern matching
            matching_files = self._glob_match(
                search_dir,
                pattern,
                case_sensitive=case_sensitive,
            )

            # Filter by ignore patterns
            for file_path in matching_files:
                if self._should_ignore_file(
                    file_path,
                    search_dir,
                ):
                    ignored_count += 1
                else:
                    all_entries.append(file_path)

        # Check if any files found
        if not all_entries:
            message = f'No files found matching pattern "{pattern}"'
            if dir_path:
                message += f" within {search_dir}"
            if ignored_count > 0:
                message += f" ({ignored_count} files were ignored)"
            self.set_output(message)
            return

        # Sort files by modification time
        now_timestamp = time.time()
        # recency_threshold_days: Number of days to consider a file "recent" for sorting (default: 1).
        recency_threshold_ms = self.op_params.get("recency_threshold_days", 1) * 24 * 60 * 60 * 1000

        def get_sort_key(path: Path) -> tuple:
            mtime = path.stat().st_mtime
            mtime_ms = mtime * 1000
            is_recent = (now_timestamp * 1000) - mtime_ms < recency_threshold_ms

            if is_recent:
                # Recent files: sort by mtime descending (newest first)
                return 0, -mtime_ms
            else:
                # Old files: sort alphabetically
                return 1, str(path)

        sorted_entries = sorted(all_entries, key=get_sort_key)

        # Format results
        sorted_absolute_paths = [str(entry.resolve()) for entry in sorted_entries]
        file_list_description = "\n".join(sorted_absolute_paths)
        file_count = len(sorted_absolute_paths)

        result_message = f'Found {file_count} file(s) matching "{pattern}"'
        if dir_path:
            result_message += f" within {search_dir}"
        if ignored_count > 0:
            result_message += f" ({ignored_count} additional files were ignored)"
        result_message += ", sorted by modification time (newest first):\n"
        result_message += file_list_description

        self.set_output(result_message)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        pattern: str = self.input_dict.get("pattern", "").strip()
        error_msg = f'Failed to search files matching pattern "{pattern}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)

    def _glob_match(
        self,
        root_dir: Path,
        pattern: str,
        case_sensitive: bool = False,
    ) -> List[Path]:
        """Match files using glob pattern.

        Args:
            root_dir: Root directory to search in.
            pattern: Glob pattern to match.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            List of matching file paths.
        """
        matching_files: List[Path] = []

        # Handle ** pattern (recursive match)
        if "**" in pattern:
            # Split pattern into parts
            parts = pattern.split("**", 1)
            prefix = parts[0].rstrip("/")
            suffix = parts[1] if len(parts) > 1 else ""

            # Walk through directory tree
            for path in root_dir.rglob("*"):
                if not path.is_file():
                    continue

                rel_path = path.relative_to(root_dir)
                rel_str = str(rel_path).replace("\\", "/")

                # Check if path matches pattern
                if self._matches_glob_pattern(
                    rel_str,
                    prefix,
                    suffix,
                    case_sensitive,
                ):
                    matching_files.append(path)
        else:
            # For patterns without **, use fnmatch for better compatibility
            # Walk through directory tree and match manually
            pattern_normalized = pattern.replace("\\", "/")
            for path in root_dir.rglob("*"):
                if not path.is_file():
                    continue

                rel_path = path.relative_to(root_dir)
                rel_str = str(rel_path).replace("\\", "/")

                # Match using fnmatch
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
        """Check if a path matches a glob pattern with **.

        Args:
            path_str: Path string to check (relative to root).
            prefix: Prefix pattern before **.
            suffix: Suffix pattern after **.
            case_sensitive: Whether matching should be case-sensitive.

        Returns:
            True if path matches pattern, False otherwise.
        """
        if not case_sensitive:
            path_str = path_str.lower()
            prefix = prefix.lower()
            suffix = suffix.lower()

        # Check prefix
        if prefix:
            if not path_str.startswith(prefix):
                return False

        # Check suffix
        if suffix:
            if not fnmatch.fnmatch(path_str, f"*{suffix}"):
                return False

        return True
