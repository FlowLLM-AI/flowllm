"""Base embedding store with abstract interface for caching and retrieval."""

from abc import abstractmethod

import numpy as np

from ..base_component import BaseComponent
from ...enumeration import ComponentEnum
from ...schema import EmbNode


class BaseEmbeddingStore(BaseComponent):
    """Abstract embedding store; subclasses implement caching and provider calls."""

    component_type = ComponentEnum.EMBEDDING_STORE

    def __init__(self, max_batch_size: int = 10, max_input_length: int = 8192, max_retries: int = 3, **kwargs):
        super().__init__(**kwargs)
        self.max_batch_size = max_batch_size
        self.max_input_length = max_input_length
        self.max_retries = max_retries
        self.is_healthy: bool = True

    @abstractmethod
    async def health_check(self, timeout: float = 2.0) -> bool:
        """Probe provider; sets and returns is_healthy."""

    async def get_embedding(self, input_text: str, **kwargs) -> np.ndarray | None:
        """Get a single embedding vector."""
        results = await self.get_embeddings([input_text], **kwargs)
        return results[0] if results else None

    @abstractmethod
    async def get_embeddings(self, input_text: list[str], **kwargs) -> list[np.ndarray | None]:
        """Get embeddings for a list of texts."""

    async def get_node_embeddings(self, nodes: list[EmbNode], **kwargs) -> list[EmbNode]:
        """Populate embedding field on EmbNode list."""
        embeddings = await self.get_embeddings([n.text for n in nodes], **kwargs)
        if len(embeddings) == len(nodes):
            for node, vec in zip(nodes, embeddings):
                if vec is not None:
                    node.embedding = vec
        return nodes
