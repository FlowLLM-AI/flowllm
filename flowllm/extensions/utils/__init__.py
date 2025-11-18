"""Utility functions for FlowLLM framework extensions.

This package provides utility functions that can be used across extension modules.
It includes date/time utilities for working with date ranges and searching,
and file editing utilities for intelligent text replacement.
"""

from .dt_utils import (
    find_dt_greater_index,
    find_dt_less_index,
    get_monday_fridays,
    next_friday_or_same,
)
from .edit_utils import (
    calculate_exact_replacement,
    calculate_flexible_replacement,
    calculate_regex_replacement,
    escape_regex,
    restore_trailing_newline,
)

__all__ = [
    "find_dt_greater_index",
    "find_dt_less_index",
    "get_monday_fridays",
    "next_friday_or_same",
    "calculate_exact_replacement",
    "calculate_flexible_replacement",
    "calculate_regex_replacement",
    "escape_regex",
    "restore_trailing_newline",
]
