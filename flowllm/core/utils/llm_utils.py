"""Utility functions for LLM-related operations.

This module provides utility functions for formatting and processing messages
for LLM interactions.
"""

import json
import re
from typing import List

from ..enumeration import Role
from ..schema import Message


def format_messages(messages: List[Message]) -> str:
    """Format messages into a readable string representation.

    Converts a list of Message objects into a simple text format where each
    message is represented as "role: content" on a separate line. This is
    useful for logging, debugging, or displaying conversation history in
    a human-readable format.

    Args:
        messages: List of Message objects to format. Each message should have
            a role and content attribute.

    Returns:
        Formatted string representation of messages, with each message on a
        new line in the format "role: content". Messages are separated by
        newline characters.

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

    Each message is prefixed with a step number (starting from 0) to indicate
    its position in the conversation sequence.

    Args:
        messages: List of Message objects or dictionaries to merge. If a dict
            is provided, it will be converted to a Message object.

    Returns:
        Formatted string representation of all messages with step numbers.
        Each message is separated by newlines and includes role information.

    Example:
        ```python
        messages = [
            Message(role=Role.USER, content="What's the weather?"),
            Message(role=Role.ASSISTANT, content="Let me check",
                    tool_calls=[ToolCall(name="get_weather", arguments={})])
        ]
        result = merge_messages_content(messages)
        # Returns formatted string with step numbers and role information
        ```
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


def extract_content(text: str, language_tag: str = "json", greedy: bool = False):
    """Extract and parse content from Markdown code blocks.

    Searches for content within Markdown code blocks (triple backticks)
    and extracts it. If the language tag is "json", attempts to parse
    the extracted content as JSON. If no code block is found, returns
    the original text (or parsed JSON if applicable).

    Args:
        text: The text to search for code blocks.
        language_tag: The language tag of the code block (e.g., "json",
            "python"). Defaults to "json". The tag matching is case-sensitive
            and allows optional whitespace around the tag.
        greedy: If False (default), uses non-greedy matching to find the
            nearest closing ```. If True, uses greedy matching to find
            the farthest closing ```. This is useful when there are multiple
            code blocks with the same language tag.

    Returns:
        If language_tag is "json":
            - Parsed JSON object/dict/list if valid JSON is found
            - None if JSON parsing fails
        Otherwise:
            - Extracted content string from code block (stripped of whitespace)
            - Original text if no code block is found

    Example:
        ```python
        extract_content("```json\\n{\"key\": \"value\"}\\n```")  # noqa
        # {'key': 'value'}
        extract_content("``` json\\n{\"key\": \"value\"}\\n```")  # noqa
        # {'key': 'value'}
        extract_content("```python\\nprint('hello')\\n```", "python")
        # "print('hello')"
        extract_content("Some text without code blocks")
        # "Some text without code blocks"
        ```
    """
    # Use non-greedy (.*?) or greedy (.*) matching based on the greedy parameter
    quantifier = ".*" if greedy else ".*?"
    pattern = rf"```\s*{re.escape(language_tag)}\s*({quantifier})\s*```"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        result = match.group(1).strip()
    else:
        result = text

    if language_tag == "json":
        try:
            result = json.loads(result)

        except json.JSONDecodeError:
            result = None

    return result


def parse_message_by_keys(content: str, keys: List[str]) -> dict:
    """Parse content by splitting it using a sequence of keys as delimiters.

    This function sequentially splits the content string using each key in the
    provided list as a delimiter. It extracts the content segments between
    consecutive keys and returns them as a dictionary where each key maps to
    its corresponding content segment.

    The parsing process works as follows:
    1. For each key in the sequence, split the remaining content at the first
       occurrence of that key
    2. Store the content before the key (for previous key) and continue with
       the content after the key
    3. For the last key, store both the content before and after it

    Args:
        content: The string content to parse
        keys: List of keys (delimiters) to use for splitting, in order

    Returns:
        Dictionary mapping each key to its corresponding content segment.
        Keys that don't appear in the content will have empty string values.
        Content before the first key is discarded.

    Example:
        ```python
        content = "prefixkey1middlekey2suffix"
        keys = ["key1", "key2"]
        result = parse_message_by_keys(content, keys)
        # Returns: {"key1": "middle", "key2": "suffix"}
        ```

    Note:
        - Only the first occurrence of each key is used for splitting
        - Content before the first key is not included in the result
        - If a key is not found, the remaining content is assigned to the
          previous key (or discarded if it's the first key)
    """
    origin_content = content
    result = {}
    # Iterate through pairs of (previous_key, current_key)
    for pre_key, key in zip([None] + keys[:-1], keys):
        # Split content at the first occurrence of current key (max 1 split)
        origin_split = origin_content.strip().split(key, 1)

        if pre_key is None:
            # First key: discard content before it, keep content after
            if len(origin_split) >= 2:
                origin_content = origin_split[1]
                # Special case: if this is the only key, store the result
                if len(keys) == 1:
                    result[key] = origin_split[1]
            else:
                # Key not found, keep original content for next iteration
                # Special case: if this is the only key and not found, store empty
                if len(keys) == 1:
                    result[key] = ""

        elif key == keys[-1]:
            # Last key: store content before it (for previous key) and after it
            if len(origin_split) >= 2:
                result[pre_key] = origin_split[0]
                result[key] = origin_split[1]
            else:
                # Key not found, assign remaining content to previous key
                result[pre_key] = origin_content
                result[key] = ""

        else:
            # Middle keys: store content before current key, continue with content after
            if len(origin_split) >= 2:
                result[pre_key] = origin_split[0]
                origin_content = origin_split[1]
            else:
                # Key not found, assign remaining content to previous key and continue
                result[pre_key] = origin_content

    return result
