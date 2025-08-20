from typing import Dict

from pydantic import BaseModel, Field

from flowllm.schema.tool_call import ToolCall


class MCPConfig(BaseModel):
    transport: str = Field(default="", description="stdio/http/sse/streamable-http")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)


class HttpConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    timeout_keep_alive: int = Field(default=600)
    limit_concurrency: int = Field(default=64)


class FlowConfig(ToolCall):
    flow_content: str = Field(default="")

    def set_name(self, name: str):
        self.name = name
        return self


class FlowEngineConfig(BaseModel):
    backend: str = Field(default="")
    params: dict = Field(default_factory=dict)


class OpConfig(BaseModel):
    backend: str = Field(default="")
    language: str = Field(default="")
    raise_exception: bool = Field(default=True)
    prompt_path: str = Field(default="")
    llm: str = Field(default="default")
    embedding_model: str = Field(default="default")
    vector_store: str = Field(default="default")
    params: dict = Field(default_factory=dict)


class LLMConfig(BaseModel):
    backend: str = Field(default="")
    model_name: str = Field(default="")
    params: dict = Field(default_factory=dict)


class EmbeddingModelConfig(BaseModel):
    backend: str = Field(default="")
    model_name: str = Field(default="")
    params: dict = Field(default_factory=dict)


class VectorStoreConfig(BaseModel):
    backend: str = Field(default="")
    embedding_model: str = Field(default="")
    params: dict = Field(default_factory=dict)


class ServiceConfig(BaseModel):
    backend: str = Field(default="")
    language: str = Field(default="")
    thread_pool_max_workers: int = Field(default=16)
    ray_max_workers: int = Field(default=8)

    mcp: MCPConfig = Field(default_factory=MCPConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    flow_engine: FlowEngineConfig = Field(default_factory=FlowEngineConfig)
    flow: Dict[str, FlowConfig] = Field(default_factory=dict)
    op: Dict[str, OpConfig] = Field(default_factory=dict)
    llm: Dict[str, LLMConfig] = Field(default_factory=dict)
    embedding_model: Dict[str, EmbeddingModelConfig] = Field(default_factory=dict)
    vector_store: Dict[str, VectorStoreConfig] = Field(default_factory=dict)
