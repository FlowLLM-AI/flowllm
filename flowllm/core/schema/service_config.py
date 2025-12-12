"""Service configuration schema definitions for various service components."""

from typing import Dict, List

from pydantic import BaseModel, Field

from .tool_call import ToolCall


class MCPConfig(BaseModel):
    """Configuration for MCP (Model Context Protocol) transport settings."""

    transport: str = Field(default="")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)


class HttpConfig(BaseModel):
    """Configuration for HTTP server settings."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    timeout_keep_alive: int = Field(default=3600)
    limit_concurrency: int = Field(default=1000)


class CmdConfig(BaseModel):
    """Configuration for command-line execution."""

    flow: str = Field(default="")
    params: dict = Field(default_factory=dict)


class FlowConfig(ToolCall):
    """Configuration for flow execution with optional streaming and caching.

    In addition to tool-call metadata inherited from `ToolCall`, this config
    controls execution behavior such as streaming output and response caching.
    Caching is only applied to non-streaming invocations.
    """

    flow_content: str = Field(default="")
    stream: bool = Field(default=False)
    enable_cache: bool = Field(default=False, description="Enable non-stream response caching")
    cache_path: str = Field(default="cache/{flow_name}", description="Cache path template; supports {flow_name}")
    cache_expire_hours: float = Field(default=0.1, description="Cache TTL (hours)")


class LLMTokenCountConfig(BaseModel):
    """Configuration for LLM token count estimation."""

    backend: str = Field(default="base")
    model_name: str = Field(default="")
    params: dict = Field(default_factory=dict)


class LLMConfig(BaseModel):
    """Configuration for LLM (Large Language Model) backend settings."""

    backend: str = Field(default="")
    model_name: str = Field(default="")
    token_count: LLMTokenCountConfig = Field(default_factory=LLMTokenCountConfig)
    params: dict = Field(default_factory=dict)


class EmbeddingModelConfig(BaseModel):
    """Configuration for embedding model backend settings."""

    backend: str = Field(default="")
    model_name: str = Field(default="")
    params: dict = Field(default_factory=dict)


class VectorStoreConfig(BaseModel):
    """Configuration for vector store backend settings."""

    backend: str = Field(default="")
    embedding_model: str = Field(default="")
    params: dict = Field(default_factory=dict)


class ServiceConfig(BaseModel):
    """Main service configuration aggregating all component configurations."""

    backend: str = Field(default="")
    enable_logo: bool = Field(default=True)
    language: str = Field(default="")
    thread_pool_max_workers: int = Field(default=16)
    ray_max_workers: int = Field(default=-1)
    init_logger: bool = Field(default=True)
    disabled_flows: List[str] = Field(default_factory=list)
    enabled_flows: List[str] = Field(default_factory=list)

    cmd: CmdConfig = Field(default_factory=CmdConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    external_mcp: Dict[str, dict] = Field(default_factory=dict, description="External MCP Server config")
    http: HttpConfig = Field(default_factory=HttpConfig)
    flow: Dict[str, FlowConfig] = Field(default_factory=dict)
    llm: Dict[str, LLMConfig] = Field(default_factory=dict)
    embedding_model: Dict[str, EmbeddingModelConfig] = Field(default_factory=dict)
    vector_store: Dict[str, VectorStoreConfig] = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
