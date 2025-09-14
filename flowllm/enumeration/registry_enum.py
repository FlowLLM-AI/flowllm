from enum import Enum


class RegistryEnum(str, Enum):
    EMBEDDING_MODEL = "embedding_model"
    LLM = "llm"
    VECTOR_STORE = "vector_store"
    OP = "op"
    FLOW = "flow"
    SERVICE = "service"
