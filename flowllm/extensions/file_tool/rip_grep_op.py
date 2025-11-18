"""Ripgrep text search operation module.

This module provides a tool operation for searching text patterns in files
using ripgrep (rg). It enables efficient content-based search using regular
expressions with support for glob pattern filtering and result limiting.
"""

import asyncio
from pathlib import Path
from typing import Optional

from ...core.context import C
from ...core.op import BaseAsyncToolOp
from ...core.schema import ToolCall


@C.register_op()
class RipGrepOp(BaseAsyncToolOp):
    """Ripgrep text search operation.

    This operation searches for text patterns in files using ripgrep (rg).
    Supports glob pattern filtering and result limiting.
    """

    file_path = __file__

    def __init__(self, **kwargs):
        kwargs.setdefault("raise_exception", False)
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        """Build and return the tool call schema for this operator."""
        tool_params = {
            "name": "RipGrep",
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
        """Execute the ripgrep search operation."""
        pattern: str = self.input_dict.get("pattern", "").strip()
        path: Optional[str] = self.input_dict.get("path")
        glob_pattern: Optional[str] = self.input_dict.get("glob")
        limit: Optional[int] = self.input_dict.get("limit")

        # Validate pattern
        if not pattern:
            raise ValueError("The 'pattern' parameter cannot be empty.")

        # Determine search path
        if path:
            search_path = Path(path).expanduser().resolve()
            if not search_path.exists():
                raise ValueError(f"Search path does not exist: {search_path}")
        else:
            search_path = Path.cwd()

        # Build ripgrep command
        rg_args = [
            "rg",
            "--line-number",
            "--no-heading",
            "--with-filename",
            "--ignore-case",
            "--regexp",
            pattern,
        ]

        # Add glob pattern if provided
        if glob_pattern:
            rg_args.extend(["--glob", glob_pattern])

        # Add search path
        rg_args.append(str(search_path))

        # Execute ripgrep
        process = await asyncio.create_subprocess_exec(
            *rg_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # Handle ripgrep exit codes
        if process.returncode == 0:
            raw_output = stdout.decode("utf-8").strip()
        elif process.returncode == 1:
            # No matches found
            raw_output = ""
        else:
            error_msg = stderr.decode("utf-8").strip()
            raise ValueError(f"ripgrep exited with code {process.returncode}: {error_msg}")

        # Build search description
        search_location = f'in path "{path}"' if path else "in the workspace directory"
        filter_desc = f' (filter: "{glob_pattern}")' if glob_pattern else ""

        # Check if we have any matches
        if not raw_output:
            result_msg = f'No matches found for pattern "{pattern}" {search_location}{filter_desc}.'
            self.set_output(result_msg)
            return

        # Split into lines and apply limit
        all_lines = [line for line in raw_output.split("\n") if line.strip()]
        total_matches = len(all_lines)
        match_term = "match" if total_matches == 1 else "matches"

        # Apply limit if specified
        lines_to_include = all_lines
        truncated = False
        if limit and len(all_lines) > limit:
            lines_to_include = all_lines[:limit]
            truncated = True

        # Build output
        header = f'Found {total_matches} {match_term} for pattern "{pattern}" {search_location}{filter_desc}:\n---\n'
        grep_output = "\n".join(lines_to_include)

        result_msg = header + grep_output
        if truncated:
            omitted = total_matches - len(lines_to_include)
            result_msg += f"\n---\n[{omitted} {'line' if omitted == 1 else 'lines'} truncated] ..."

        self.set_output(result_msg)

    async def async_default_execute(self, e: Exception = None, **kwargs):
        """Fill outputs with a default failure message when execution fails."""
        pattern: str = self.input_dict.get("pattern", "").strip()
        error_msg = f'Failed to search for pattern "{pattern}"'
        if e:
            error_msg += f": {str(e)}"
        self.set_output(error_msg)
