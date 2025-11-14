"""File tool package for FlowLLM framework.

This package provides file-related operations that can be used in LLM-powered flows.
It includes ready-to-use operations for:

- EditOp: File editing operation for replacing text within files
- GlobOp: File search operation for finding files matching glob patterns
"""

from .edit_op import EditOp
from .glob_op import GlobOp

__all__ = [
    "EditOp",
    "GlobOp",
]
