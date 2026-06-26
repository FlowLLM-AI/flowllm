"""Component type enumeration."""

from enum import Enum


class ComponentEnum(str, Enum):
    """Component types for dependency injection."""

    BASE = "base"

    AS_LLM = "as_llm"

    AS_EMBEDDING = "as_embedding"

    EMBEDDING_STORE = "embedding_store"

    FILE_CHUNKER = "file_chunker"

    FILE_STORE = "file_store"

    FILE_GRAPH = "file_graph"

    FILE_CATALOG = "file_catalog"

    KEYWORD_INDEX = "keyword_index"

    SERVICE = "service"

    CLIENT = "client"

    STEP = "step"

    JOB = "job"

    TOKENIZER = "tokenizer"

    AGENT_WRAPPER = "agent_wrapper"
