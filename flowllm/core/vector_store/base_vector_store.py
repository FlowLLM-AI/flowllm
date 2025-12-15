"""Base class for vector store implementations.

This module provides the abstract base class for vector stores, which are used
to store, search, and manage vector embeddings along with their associated metadata.
Vector stores support workspace-based organization and provide both synchronous
and asynchronous interfaces for all operations.
"""

import asyncio
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import List, Dict, Any, Optional
from types import TracebackType

from ..context.service_context import C
from ..embedding_model import BaseEmbeddingModel
from ..schema import VectorNode


class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations.

    This class defines the interface that all vector store implementations must
    follow. It provides methods for managing workspaces, inserting and searching
    vector nodes, and exporting/importing data. Both synchronous and asynchronous
    versions of all operations are available.

    Attributes:
        embedding_model: Optional embedding model used for generating embeddings
            from text queries. If None, nodes must be inserted with pre-computed
            embeddings.

    Subclasses must implement all abstract methods to provide the actual vector
    storage functionality.
    """

    def __init__(self, embedding_model: BaseEmbeddingModel | None = None, **kwargs):
        # Initialize the vector store with an optional embedding model
        self.embedding_model: BaseEmbeddingModel | None = embedding_model
        self.kwargs: dict = kwargs

    @staticmethod
    async def _run_sync_in_executor(sync_func, *args, **kwargs):
        """Run a synchronous function in a thread pool executor.

        This utility method is useful for wrapping synchronous I/O operations
        (like file reads/writes) in async methods to avoid blocking the event loop.

        Args:
            sync_func: The synchronous function to execute.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The return value of the synchronous function.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(C.thread_pool, partial(sync_func, *args, **kwargs))

    def get_node_embeddings(self, nodes: VectorNode | List[VectorNode]) -> List[VectorNode]:
        """Generate embeddings for nodes using the embedding model.

        Args:
            nodes: Single VectorNode or list of VectorNodes to generate embeddings for.

        Returns:
            List[VectorNode]: List of VectorNodes with generated embeddings.

        Raises:
            ValueError: If embedding_model is None.
        """
        if self.embedding_model is None:
            raise ValueError("embedding_model is None. Cannot generate embeddings without an embedding model.")
        return self.embedding_model.get_node_embeddings(nodes)

    async def async_get_node_embeddings(self, nodes: VectorNode | List[VectorNode]) -> List[VectorNode]:
        """Asynchronously generate embeddings for nodes using the embedding model.

        Args:
            nodes: Single VectorNode or list of VectorNodes to generate embeddings for.

        Returns:
            List[VectorNode]: List of VectorNodes with generated embeddings.

        Raises:
            ValueError: If embedding_model is None.
        """
        if self.embedding_model is None:
            raise ValueError("embedding_model is None. Cannot generate embeddings without an embedding model.")
        return await self.embedding_model.async_get_node_embeddings(nodes)

    def get_embeddings(self, query: str | List[str]):
        """Generate embeddings for text queries using the embedding model.

        Args:
            query: Single string or list of strings to generate embeddings for.

        Returns:
            Embeddings for the input query/queries.

        Raises:
            ValueError: If embedding_model is None.
        """
        if self.embedding_model is None:
            raise ValueError("embedding_model is None. Cannot generate embeddings without an embedding model.")
        return self.embedding_model.get_embeddings(query)

    async def async_get_embeddings(self, query: str | List[str]):
        """Asynchronously generate embeddings for text queries using the embedding model.

        Args:
            query: Single string or list of strings to generate embeddings for.

        Returns:
            Embeddings for the input query/queries.

        Raises:
            ValueError: If embedding_model is None.
        """
        if self.embedding_model is None:
            raise ValueError("embedding_model is None. Cannot generate embeddings without an embedding model.")
        return await self.embedding_model.async_get_embeddings(query)

    @abstractmethod
    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a workspace exists in the vector store."""

    @abstractmethod
    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Asynchronously check if a workspace exists in the vector store."""

    @abstractmethod
    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a workspace from the vector store."""

    @abstractmethod
    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Asynchronously delete a workspace from the vector store."""

    @abstractmethod
    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new workspace in the vector store."""

    @abstractmethod
    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Asynchronously create a new workspace in the vector store."""

    @abstractmethod
    def list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """List all nodes in a workspace."""

    @abstractmethod
    async def async_list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """Asynchronously list all nodes in a workspace."""

    @abstractmethod
    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Dump workspace data to a file or path."""

    @abstractmethod
    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Asynchronously dump workspace data to a file or path."""

    @abstractmethod
    def load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] | None = None,
        callback_fn=None,
        **kwargs,
    ):
        """Load workspace data from a file or path, or from provided nodes."""

    @abstractmethod
    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] | None = None,
        callback_fn=None,
        **kwargs,
    ):
        """Asynchronously load workspace data from a file or path, or from provided nodes."""

    @abstractmethod
    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Copy one workspace to another."""

    @abstractmethod
    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Asynchronously copy one workspace to another."""

    @abstractmethod
    def list_workspace(self, **kwargs) -> List[str]:
        """List all existing workspaces."""

    @abstractmethod
    async def async_list_workspace(self, **kwargs) -> List[str]:
        """Asynchronously list all existing workspaces."""

    @abstractmethod
    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vectors in the workspace.

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking. In this case,
        results are returned based solely on filter_dict criteria, up to top_k
        items, without similarity scores.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments for implementation-specific options.

        Returns:
            List[VectorNode]: List of matching nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a
                "score" key in metadata. When query is empty, nodes are returned
                in storage order without scores.
        """

    @abstractmethod
    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vectors in the workspace.

        Async version of search(). When query is empty, degrades to filter-only
        search without vector similarity ranking.

        See search() for full documentation.
        """

    @abstractmethod
    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Insert nodes into the workspace."""

    @abstractmethod
    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Asynchronously insert nodes into the workspace."""

    @abstractmethod
    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Delete nodes from the workspace by their IDs."""

    @abstractmethod
    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Asynchronously delete nodes from the workspace by their IDs."""

    def close(self):
        """Close the vector store and clean up resources."""

    async def async_close(self):
        """Asynchronously close the vector store and clean up resources."""

    def __enter__(self) -> "BaseVectorStore":
        """Allow usage as a synchronous context manager."""
        return self

    async def __aenter__(self) -> "BaseVectorStore":
        """Allow usage as an asynchronous context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Ensure resources close when exiting a sync context."""
        self.close()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Ensure resources close when exiting an async context."""
        await self.async_close()
