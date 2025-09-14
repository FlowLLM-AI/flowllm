from typing import Dict, List

from pydantic import BaseModel, Field

from flowllm.schema.tool_call import ToolCall


class MCPConfig(BaseModel):
    transport: str = Field(default="", description="stdio/http/sse")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)


class HttpConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    timeout_keep_alive: int = Field(default=3600)
    limit_concurrency: int = Field(default=1000)


class CmdConfig(BaseModel):
    flow: str = Field(default="")
    params: dict = Field(default_factory=dict)


class FlowConfig(ToolCall):
    flow_content: str = Field(default="")
    stream: bool = Field(default=False)


class OpConfig(BaseModel):
    backend: str = Field(default="")
    language: str = Field(default="")
    max_retries: int = Field(default=1)
    raise_exception: bool = Field(default=True)
    prompt_path: str = Field(default="")
    llm: str = Field(default="")
    embedding_model: str = Field(default="")
    vector_store: str = Field(default="")
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
    enable_logo: bool = Field(default=True)
    language: str = Field(default="")
    thread_pool_max_workers: int = Field(default=16)
    ray_max_workers: int = Field(default=-1)
    import_config: str = Field(default="", description="Import the configuration in the same path as the base")
    init_logger: bool = Field(default=True)
    disabled_flows: List[str] = Field(default_factory=list)
    enabled_flows: List[str] = Field(default_factory=list)

    cmd: CmdConfig = Field(default_factory=CmdConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    external_mcp: Dict[str, dict] = Field(default_factory=dict, description="External MCP Server config")
    http: HttpConfig = Field(default_factory=HttpConfig)
    flow: Dict[str, FlowConfig] = Field(default_factory=dict)
    op: Dict[str, OpConfig] = Field(default_factory=dict)
    llm: Dict[str, LLMConfig] = Field(default_factory=dict)
    embedding_model: Dict[str, EmbeddingModelConfig] = Field(default_factory=dict)
    vector_store: Dict[str, VectorStoreConfig] = Field(default_factory=dict)
