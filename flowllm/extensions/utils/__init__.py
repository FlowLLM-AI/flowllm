"""Utility functions for FlowLLM framework extensions.

This package provides utility functions that can be used across extension modules.
It includes file editing utilities for intelligent text replacement.
"""

from .edit_utils import (
    calculate_exact_replacement,
    calculate_flexible_replacement,
    calculate_regex_replacement,
    escape_regex,
    restore_trailing_newline,
)

__all__ = [
    "calculate_exact_replacement",
    "calculate_flexible_replacement",
    "calculate_regex_replacement",
    "escape_regex",
    "restore_trailing_newline",
]
