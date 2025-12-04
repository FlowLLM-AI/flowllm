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
from typing import List, Iterable, Dict, Any, Optional

from ..context import C
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
        self.embedding_model: BaseEmbeddingModel | None = embedding_model
        self.kwargs: dict = kwargs

    @abstractmethod
    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a workspace exists in the vector store."""
        raise NotImplementedError

    @abstractmethod
    def delete_workspace(self, workspace_id: str, **kwargs) -> None:
        """Delete a workspace from the vector store."""
        raise NotImplementedError

    @abstractmethod
    def create_workspace(self, workspace_id: str, **kwargs) -> None:
        """Create a new workspace in the vector store."""
        raise NotImplementedError

    @abstractmethod
    def iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace."""
        raise NotImplementedError

    @abstractmethod
    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs) -> None:
        """Dump workspace data to a file or path."""
        raise NotImplementedError

    @abstractmethod
    def load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: Optional[List[VectorNode]] = None,
        callback_fn=None,
        **kwargs,
    ) -> None:
        """Load workspace data from a file or path, or from provided nodes."""
        raise NotImplementedError

    @abstractmethod
    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs) -> None:
        """Copy one workspace to another."""
        raise NotImplementedError

    @abstractmethod
    def list_workspace(self, **kwargs) -> List[str]:
        """List all existing workspaces.

        Returns:
            List[str]: A list of workspace identifiers available in this vector store.
        """
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vectors in the workspace."""
        raise NotImplementedError

    @abstractmethod
    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs) -> None:
        """Insert nodes into the workspace."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs) -> None:
        """Delete nodes from the workspace by their IDs."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the vector store and clean up resources. Default implementation does nothing."""

    # Async versions of all methods

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace.

        Args:
            workspace_id: The ID of the workspace to check.
            **kwargs: Additional keyword arguments passed to the underlying implementation.

        Returns:
            True if the workspace exists, False otherwise.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.exist_workspace, workspace_id, **kwargs))

    async def async_delete_workspace(self, workspace_id: str, **kwargs) -> None:
        """Async version of delete_workspace.

        Args:
            workspace_id: The ID of the workspace to delete.
            **kwargs: Additional keyword arguments passed to the underlying implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.delete_workspace, workspace_id, **kwargs))

    async def async_create_workspace(self, workspace_id: str, **kwargs) -> None:
        """Async version of create_workspace.

        Args:
            workspace_id: The ID of the workspace to create.
            **kwargs: Additional keyword arguments passed to the underlying implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.create_workspace, workspace_id, **kwargs))

    async def async_iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        """Async version of iter_workspace_nodes.

        Args:
            workspace_id: The ID of the workspace to iterate nodes from.
            **kwargs: Additional keyword arguments passed to the underlying implementation.

        Returns:
            An iterable of VectorNode objects from the workspace.

        Note:
            This method returns an iterable, not an async iterator. The iteration happens
            synchronously in a thread pool executor.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(
                self.iter_workspace_nodes,
                workspace_id,
                **kwargs,
            ),
        )

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Async version of dump_workspace.

        Args:
            workspace_id: The ID of the workspace to dump.
            path: The file or directory path where the workspace data should be saved.
            callback_fn: Optional callback function to be called during the dump process.
            **kwargs: Additional keyword arguments passed to the underlying implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(
                self.dump_workspace,
                workspace_id,
                path,
                callback_fn,
                **kwargs,
            ),
        )

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] = None,
        callback_fn=None,
        **kwargs,
    ):
        """Async version of load_workspace.

        Args:
            workspace_id: The ID of the workspace to load data into.
            path: The file or directory path to load workspace data from.
            nodes: Optional list of VectorNode objects to load directly.
            callback_fn: Optional callback function to be called during the load process.
            **kwargs: Additional keyword arguments passed to the underlying implementation.

        Note:
            Either `path` or `nodes` should be provided, but not both.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(
                self.load_workspace,
                workspace_id,
                path,
                nodes,
                callback_fn,
                **kwargs,
            ),
        )

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Async version of copy_workspace.

        Args:
            src_workspace_id: The ID of the source workspace to copy from.
            dest_workspace_id: The ID of the destination workspace to copy to.
            **kwargs: Additional keyword arguments passed to the underlying implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(
                self.copy_workspace,
                src_workspace_id,
                dest_workspace_id,
                **kwargs,
            ),
        )

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: dict = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Async version of search.

        Args:
            query: The search query string. Will be embedded using the embedding_model
                if one is configured.
            workspace_id: The ID of the workspace to search in.
            top_k: The number of most similar results to return (default: 1).
            filter_dict: Optional dictionary of filters to apply to the search.
            **kwargs: Additional keyword arguments passed to the underlying implementation.

        Returns:
            A list of VectorNode objects matching the query, sorted by similarity.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(
                self.search,
                query,
                workspace_id,
                top_k,
                filter_dict,
                **kwargs,
            ),
        )

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert.

        Args:
            nodes: A single VectorNode or a list of VectorNode objects to insert.
            workspace_id: The ID of the workspace to insert nodes into.
            **kwargs: Additional keyword arguments passed to the underlying implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.insert, nodes, workspace_id, **kwargs))

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete.

        Args:
            node_ids: A single node ID or a list of node IDs to delete.
            workspace_id: The ID of the workspace containing the nodes to delete.
            **kwargs: Additional keyword arguments passed to the underlying implementation.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.delete, node_ids, workspace_id, **kwargs))

    async def async_close(self):
        """Async version of close.

        Closes the vector store and cleans up resources asynchronously.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, self.close)
