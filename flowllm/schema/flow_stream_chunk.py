from pydantic import Field, BaseModel

from flowllm.enumeration.chunk_enum import ChunkEnum


class FlowStreamChunk(BaseModel):
    flow_id: str = Field(default="")
    chunk_type: ChunkEnum = Field(default=ChunkEnum.ANSWER)
    chunk: str | bytes = Field(default="")
    done: bool = Field(default=False)
    metadata: dict = Field(default_factory=dict)
