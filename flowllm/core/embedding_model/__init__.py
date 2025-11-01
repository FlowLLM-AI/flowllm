"""Embedding model implementations for FlowLLM.

This module provides base classes and concrete implementations for embedding models,
supporting both synchronous and asynchronous operations with retry logic and batch processing.
"""

from .base_embedding_model import BaseEmbeddingModel
from .openai_compatible_embedding_model import OpenAICompatibleEmbeddingModel

__all__ = [
    "BaseEmbeddingModel",
    "OpenAICompatibleEmbeddingModel",
]
