"""Grep text search operation module.

This module provides a tool operation for searching text patterns in files.
It enables efficient content-based search using regular expressions, with support
for glob pattern filtering and result limiting.
"""

import fnmatch
import re
from pathlib import Path
from typing import List, Optional

from loguru import logger

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class GrepOp(BaseAsyncToolOp):
    """Grep text search operation.

    This operation searches for text patterns in files using regular expressions.
    Supports glob pattern filtering and result limiting.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "Grep",
            "description": self.get_prompt("tool_desc"),
            "input_schema": {
                "pattern": {
                    "type": "string",
                    "description": self.get_prompt("pattern"),
                    "required": True,
                },
                "path": {
                    "type": "string",
                    "description": self.get_prompt("path"),
                    "required": False,
                },
                "glob": {
                    "type": "string",
                    "description": self.get_prompt("glob"),
                    "required": False,
                },
                "limit": {
                    "type": "number",
                    "description": self.get_prompt("limit"),
                    "required": False,
                },
            },
        }

        return ToolCall(**tool_params)

    async def async_execute(self):
        """Execute the grep search operation."""
        pattern: str = self.input_dict.get("pattern", "").strip()
        path: Optional[str] = self.input_dict.get("path")
        glob_pattern: Optional[str] = self.input_dict.get("glob")
        limit: Optional[int] = self.input_dict.get("limit")

        # Validate pattern
        if not pattern:
            raise ValueError("The 'pattern' parameter cannot be empty.")

        # Validate regex pattern
        regex = re.compile(pattern, re.IGNORECASE)

        # Determine search directory
        if path:
            search_dir = Path(path).expanduser().resolve()
            if not search_dir.exists():
                raise ValueError(f"Search path does not exist: {search_dir}")
            if not search_dir.is_dir():
                raise ValueError(f"Search path is not a directory: {search_dir}")
        else:
            search_dir = Path.cwd()

        # Collect matching files based on glob pattern
        files_to_search: List[Path] = []
        if glob_pattern:
            # Use glob pattern to filter files
            glob_normalized = glob_pattern.replace("\\", "/")
            for file_path in search_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                rel_path = file_path.relative_to(search_dir)
                rel_str = str(rel_path).replace("\\", "/")
                if fnmatch.fnmatch(rel_str.lower(), glob_normalized.lower()):
                    files_to_search.append(file_path)
        else:
            # Search all files recursively
            files_to_search = [f for f in search_dir.rglob("*") if f.is_file()]

        # Search for matches
        matches: List[dict] = []
        for file_path in files_to_search:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.split("\n")
                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        try:
                            relative_path = file_path.relative_to(search_dir)
                        except ValueError:
                            relative_path = file_path.name
                        matches.append(
                            {
                                "file_path": str(relative_path),
                                "line_number": line_num,
                                "line": line,
                            },
                        )
                        if limit and len(matches) >= limit:
                            break
                if limit and len(matches) >= limit:
                    break
            except Exception as e:
                logger.debug(f"Could not read {file_path}: {str(e)}")
                continue

        # Format results
        if not matches:
            search_location = f'in path "{path}"' if path else "in the workspace directory"
            filter_desc = f' (filter: "{glob_pattern}")' if glob_pattern else ""
            result_msg = f'No matches found for pattern "{pattern}" {search_location}{filter_desc}.'
            self.set_output(result_msg)
            return

        # Group matches by file
        matches_by_file = {}
        for match in matches:
            file_key = match["file_path"]
            if file_key not in matches_by_file:
                matches_by_file[file_key] = []
            matches_by_file[file_key].append(match)

        # Build output
        total_matches = len(matches)
        match_term = "match" if total_matches == 1 else "matches"
        search_location = f'in path "{path}"' if path else "in the workspace directory"
        filter_desc = f' (filter: "{glob_pattern}")' if glob_pattern else ""

        output_lines = [
            f'Found {total_matches} {match_term} for pattern "{pattern}" {search_location}{filter_desc}:\n---',
        ]

        for file_path in sorted(matches_by_file.keys()):
            output_lines.append(f"File: {file_path}")
            for match in sorted(matches_by_file[file_path], key=lambda x: x["line_number"]):
                trimmed_line = match["line"].strip()
                output_lines.append(f"L{match['line_number']}: {trimmed_line}")
            output_lines.append("---")

        result_msg = "\n".join(output_lines)
        self.set_output(result_msg)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        pattern: str = self.input_dict.get("pattern", "").strip()
        error_msg = f'Failed to search for pattern "{pattern}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
