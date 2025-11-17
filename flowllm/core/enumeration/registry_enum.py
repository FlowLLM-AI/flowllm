"""Registry enumeration for component types."""

from enum import Enum


class RegistryEnum(str, Enum):
    """Enumeration of registry types for different components."""

    EMBEDDING_MODEL = "embedding_model"
    LLM = "llm"
    VECTOR_STORE = "vector_store"
    OP = "op"
    FLOW = "flow"
    SERVICE = "service"
    TOKEN_COUNTER = "token_counter"
