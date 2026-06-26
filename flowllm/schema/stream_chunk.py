"""Stream chunk schema for incremental LLM responses."""

from typing import Any

from pydantic import BaseModel, Field

from ..enumeration import ChunkEnum


class StreamChunk(BaseModel):
    """A single chunk in a streaming response sequence."""

    chunk_type: ChunkEnum = Field(default=ChunkEnum.CONTENT, description="Type of chunk content")
    chunk: str | dict | list = Field(default="", description="Chunk payload")
    done: bool = Field(default=False, description="Whether this is the final chunk")

    session_id: str | None = Field(default=None, description="Session identifier")
    block_id: str | None = Field(default=None, description="Content block identifier")
    tool_call_id: str | None = Field(default=None, description="Tool call identifier")
    tool_call_name: str | None = Field(default=None, description="Tool call name")
    media_type: str | None = Field(default=None, description="MIME type for data blocks")
    input_tokens: int | None = Field(default=None, description="Prompt tokens consumed")
    output_tokens: int | None = Field(default=None, description="Completion tokens generated")

    metadata: dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
