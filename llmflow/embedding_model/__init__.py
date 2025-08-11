from llmflow.utils.registry import Registry

EMBEDDING_MODEL_REGISTRY = Registry()

from llmflow.embedding_model.openai_compatible_embedding_model import OpenAICompatibleEmbeddingModel
