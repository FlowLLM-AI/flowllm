"""Role enumeration for chat message roles."""

from enum import Enum


class Role(str, Enum):
    """Enumeration of roles used in chat messages."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
