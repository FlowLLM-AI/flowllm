"""Chunk type enumeration for stream processing."""

from enum import Enum


class ChunkEnum(str, Enum):
    """Chunk categories for streaming responses."""

    REPLY_START = "reply_start"
    REPLY_END = "reply_end"

    THINK = "think"
    CONTENT = "content"
    DATA = "data"

    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"

    USAGE = "usage"
    ERROR = "error"
    DONE = "done"
