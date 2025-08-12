from dataclasses import dataclass, field
from typing import Dict


@dataclass
class MCPConfig:
    transport: str = field(default="sse", metadata={"description": "stdio/sse"})
    host: str = field(default="0.0.0.0")
    port: int = field(default=8001)


@dataclass
class HttpConfig:
    host: str = field(default="0.0.0.0")
    port: int = field(default=8001)
    timeout_keep_alive: int = field(default=600)
    limit_concurrency: int = field(default=64)


@dataclass
class FlowConfig:
    backend: str = field(default="")
    flow_dict: Dict[str, str] = field(default_factory=dict)


@dataclass
class OpConfig:
    backend: str = field(default="")
    prompt_path: str = field(default="")
    llm: str = field(default="")
    embedding_model: str = field(default="")
    vector_store: str = field(default="")
    params: dict = field(default_factory=dict)


@dataclass
class LLMConfig:
    backend: str = field(default="")
    model_name: str = field(default="")
    params: dict = field(default_factory=dict)


@dataclass
class EmbeddingModelConfig:
    backend: str = field(default="")
    model_name: str = field(default="")
    params: dict = field(default_factory=dict)


@dataclass
class VectorStoreConfig:
    backend: str = field(default="")
    embedding_model: str = field(default="")
    params: dict = field(default_factory=dict)


@dataclass
class ServiceConfig:
    language: str = field(default="")
    config_path: str = field(default="")
    thread_pool_max_workers: int = field(default=16)
    ray_max_workers: int = field(default=8)

    mcp: MCPConfig = field(default_factory=MCPConfig)
    http: HttpConfig = field(default_factory=HttpConfig)
    flow: FlowConfig = field(default_factory=FlowConfig)
    op: Dict[str, OpConfig] = field(default_factory=dict)
    llm: Dict[str, LLMConfig] = field(default_factory=dict)
    embedding_model: Dict[str, EmbeddingModelConfig] = field(default_factory=dict)
    vector_store: Dict[str, VectorStoreConfig] = field(default_factory=dict)
