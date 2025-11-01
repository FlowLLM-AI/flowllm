"""Flow stream chunk schema for streaming responses."""

from typing import Union, Any

from pydantic import Field, BaseModel

from ..enumeration import ChunkEnum


class FlowStreamChunk(BaseModel):
    """Represents a chunk of streaming flow output."""

    flow_id: str = Field(default="")
    chunk_type: ChunkEnum = Field(default=ChunkEnum.ANSWER)
    chunk: Union[str, bytes, Any] = Field(
        default="",
        description="Chunk content (string, bytes, or object like ToolCall/usage)",
    )
    done: bool = Field(default=False)
    metadata: dict = Field(default_factory=dict)
