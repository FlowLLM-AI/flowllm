"""Chunk type enumeration for stream responses."""

from enum import Enum


class ChunkEnum(str, Enum):
    """Enumeration of chunk types in stream responses."""

    THINK = "think"
    ANSWER = "answer"
    TOOL = "tool"
    USAGE = "usage"
    ERROR = "error"
    DONE = "done"
