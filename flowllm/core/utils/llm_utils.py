"""Utility functions for LLM-related operations.

This module provides utility functions for formatting and processing messages
for LLM interactions.
"""

from typing import List

from ..enumeration import Role
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


def merge_messages_content(messages: List[Message | dict]) -> str:
    """Merge messages content into a formatted string representation.

    This function processes a list of messages (either Message objects or dicts)
    and formats them into a structured string. Different message roles are
    formatted differently:
    - ASSISTANT: Includes reasoning content, main content, and tool calls
    - USER: Includes the user content
    - TOOL: Includes tool call results

    Args:
        messages: List of Message objects or dictionaries to merge

    Returns:
        Formatted string representation of all messages with step numbers
    """
    content_collector = []
    for i, message in enumerate(messages):
        if isinstance(message, dict):
            message = Message(**message)

        if message.role is Role.ASSISTANT:
            line = (
                f"### step.{i} role={message.role.value} content=\n{message.reasoning_content}\n\n{message.content}\n"
            )
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    line += f" - tool call={tool_call.name}\n   params={tool_call.arguments}\n"
            content_collector.append(line)

        elif message.role is Role.USER:
            line = f"### step.{i} role={message.role.value} content=\n{message.content}\n"
            content_collector.append(line)

        elif message.role is Role.TOOL:
            line = f"### step.{i} role={message.role.value} tool call result=\n{message.content}\n"
            content_collector.append(line)

    return "\n".join(content_collector)
