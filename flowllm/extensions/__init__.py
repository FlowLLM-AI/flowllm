"""Extension packages for FlowLLM framework.

This package provides extension modules that can be used in LLM-powered flows.
It includes ready-to-use extension packages for:

- file_tool: File-related operations including editing and searching files
"""

from . import file_tool

__all__ = [
    "file_tool",
]
