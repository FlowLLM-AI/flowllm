"""Base embedding model implementation.

This module provides the abstract base class for embedding models with common
functionality including retry logic, error handling, and batch processing.
"""

import asyncio
from abc import ABC
from typing import List

from loguru import logger

from ..schema import VectorNode


class BaseEmbeddingModel(ABC):
    """
    Abstract base class for embedding models.

    This class provides a common interface for various embedding model implementations,
    including retry logic, error handling, and batch processing capabilities.
    """

    def __init__(
        self,
        model_name: str = "",
        dimensions: int = 1024,
        max_batch_size: int = 10,
        max_retries: int = 3,
        raise_exception: bool = True,
        **kwargs,
    ):
        """
        Initialize the embedding model.

        Args:
            model_name: Name of the embedding model
            dimensions: Dimensionality of the embedding vectors
            max_batch_size: Maximum batch size for processing
            max_retries: Maximum number of retry attempts on failure
            raise_exception: Whether to raise exceptions after max retries
        """
        self.model_name: str = model_name
        self.dimensions: int = dimensions
        self.max_batch_size: int = max_batch_size
        self.max_retries: int = max_retries
        self.raise_exception: bool = raise_exception
        self.kwargs: dict = kwargs

    def _get_embeddings(self, input_text: str | List[str]):
        """
        Abstract method to get embeddings from the model.

        This method must be implemented by concrete subclasses to provide
        the actual embedding functionality.

        Args:
            input_text: Single text string or list of text strings to embed

        Returns:
            Embedding vector(s) corresponding to the input text(s)
        """
        raise NotImplementedError

    async def _async_get_embeddings(self, input_text: str | List[str]):
        """
        Abstract async method to get embeddings from the model.

        This method must be implemented by concrete subclasses to provide
        the actual async embedding functionality.

        Args:
            input_text: Single text string or list of text strings to embed

        Returns:
            Embedding vector(s) corresponding to the input text(s)
        """
        raise NotImplementedError

    def get_embeddings(self, input_text: str | List[str]):
        """
        Get embeddings with retry logic and error handling.

        This method wraps the _get_embeddings method with automatic retry
        functionality in case of failures.

        Args:
            input_text: Single text string or list of text strings to embed

        Returns:
            Embedding vector(s) or None if all retries failed and raise_exception is False
        """
        # Retry loop with exponential backoff potential
        for i in range(self.max_retries):
            try:
                return self._get_embeddings(input_text)

            except Exception as e:
                logger.exception(f"embedding model name={self.model_name} encounter error with e={e.args}")
                # If this is the last retry and raise_exception is True, re-raise the exception
                if i == self.max_retries - 1 and self.raise_exception:
                    raise e

        # Return None if all retries failed and raise_exception is False
        return None

    async def async_get_embeddings(self, input_text: str | List[str]):
        """
        Get embeddings asynchronously with retry logic and error handling.

        This method wraps the _get_embeddings_async method with automatic retry
        functionality in case of failures.

        Args:
            input_text: Single text string or list of text strings to embed

        Returns:
            Embedding vector(s) or None if all retries failed and raise_exception is False
        """
        # Retry loop with exponential backoff potential
        for i in range(self.max_retries):
            try:
                return await self._async_get_embeddings(input_text)

            except Exception as e:
                logger.exception(f"embedding model name={self.model_name} encounter error with e={e.args}")
                # If this is the last retry and raise_exception is True, re-raise the exception
                if i == self.max_retries - 1 and self.raise_exception:
                    raise e

        # Return None if all retries failed and raise_exception is False
        return None

    def get_node_embeddings(self, nodes: VectorNode | List[VectorNode]):
        """
        Generate embeddings for VectorNode objects and update their vector fields.

        This method handles both single nodes and lists of nodes, with automatic
        batching for efficient processing of large node lists.

        Args:
            nodes: Single VectorNode or list of VectorNode objects to embed

        Returns:
            The same node(s) with updated vector fields containing embeddings

        Raises:
            RuntimeError: If unsupported node type is provided
        """
        # Handle single VectorNode
        if isinstance(nodes, VectorNode):
            nodes.vector = self.get_embeddings(nodes.content)
            return nodes

        # Handle list of VectorNodes with batch processing
        elif isinstance(nodes, list):
            # Process nodes in batches to respect max_batch_size limits
            embeddings = [
                emb
                for i in range(0, len(nodes), self.max_batch_size)
                for emb in self.get_embeddings(input_text=[node.content for node in nodes[i : i + self.max_batch_size]])
            ]

            # Validate that we got the expected number of embeddings
            if len(embeddings) != len(nodes):
                logger.warning(f"embeddings.size={len(embeddings)} <> nodes.size={len(nodes)}")
            else:
                # Assign embeddings to corresponding nodes
                for node, embedding in zip(nodes, embeddings):
                    node.vector = embedding
            return nodes

        else:
            raise TypeError(f"unsupported type={type(nodes)}")

    async def async_get_node_embeddings(self, nodes: VectorNode | List[VectorNode]):
        """
        Generate embeddings asynchronously for VectorNode objects and update their vector fields.

        This method handles both single nodes and lists of nodes, with automatic
        batching for efficient processing of large node lists.

        Args:
            nodes: Single VectorNode or list of VectorNode objects to embed

        Returns:
            The same node(s) with updated vector fields containing embeddings

        Raises:
            RuntimeError: If unsupported node type is provided
        """
        # Handle single VectorNode
        if isinstance(nodes, VectorNode):
            nodes.vector = await self.async_get_embeddings(nodes.content)
            return nodes

        # Handle list of VectorNodes with batch processing
        elif isinstance(nodes, list):
            # Process nodes in batches to respect max_batch_size limits
            batch_tasks = []
            for i in range(0, len(nodes), self.max_batch_size):
                batch_nodes = nodes[i : i + self.max_batch_size]
                batch_content = [node.content for node in batch_nodes]
                batch_tasks.append(self.async_get_embeddings(batch_content))

            # Execute all batch tasks concurrently
            batch_results = await asyncio.gather(*batch_tasks)

            # Flatten the results
            embeddings = [emb for batch_result in batch_results for emb in batch_result]

            # Validate that we got the expected number of embeddings
            if len(embeddings) != len(nodes):
                logger.warning(f"embeddings.size={len(embeddings)} <> nodes.size={len(nodes)}")
            else:
                # Assign embeddings to corresponding nodes
                for node, embedding in zip(nodes, embeddings):
                    node.vector = embedding
            return nodes

        else:
            raise TypeError(f"unsupported type={type(nodes)}")

    def close(self):
        """Close the client connection or clean up resources."""

    async def async_close(self):
        """Asynchronously close the client connection or clean up resources."""
