"""Utility functions for LLM-related operations.

This module provides utility functions for formatting and processing messages
for LLM interactions.
"""

from typing import List

from ..schema import Message


def format_messages(messages: List[Message]) -> str:
    """Format messages into a readable string representation.

    Args:
        messages: List of Message objects to format

    Returns:
        Formatted string representation of messages

    Example:
        ```python
        messages = [
            Message(role=Role.USER, content="Hello"),
            Message(role=Role.ASSISTANT, content="Hi there!")
        ]
        formatted = format_messages(messages)
        # Returns: "user: Hello\nassistant: Hi there!"
        ```
    """
    formatted_lines = []
    for msg in messages:
        formatted_lines.append(f"{msg.role.value}: {msg.content}")
    return "\n".join(formatted_lines)
