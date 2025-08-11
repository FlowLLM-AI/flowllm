from flowllm.utils.registry import Registry

EMBEDDING_MODEL_REGISTRY = Registry()

from flowllm.embedding_model.openai_compatible_embedding_model import OpenAICompatibleEmbeddingModel
