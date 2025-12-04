"""
ChromaDB vector store implementation.

This module provides a ChromaDB-based vector store that stores vector nodes
in ChromaDB collections. It supports workspace management, vector similarity search,
metadata filtering, and provides both synchronous and asynchronous operations.
"""

import asyncio
import os
from functools import partial
from typing import List, Iterable, Dict, Any, Optional

from loguru import logger

from .local_vector_store import LocalVectorStore
from ..context import C
from ..schema import VectorNode

# Disable ChromaDB telemetry to avoid PostHog warnings
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")


@C.register_vector_store("chroma")
class ChromaVectorStore(LocalVectorStore):
    """ChromaDB vector store implementation.

    This class provides a ChromaDB-based vector store that uses ChromaDB collections
    for workspace management. Each workspace corresponds to a ChromaDB collection,
    and vector nodes are stored with their embeddings, documents, and metadata.

    Attributes:
        store_dir: Directory path where ChromaDB data is persisted (default: "./chroma_vector_store").
        collections: Dictionary mapping workspace_id to ChromaDB Collection objects.
        _client: Private ChromaDB client instance.

    The store supports both synchronous and asynchronous operations, with async methods
    using thread pools to execute ChromaDB operations without blocking the event loop.
    """

    def __init__(self, store_dir: str = "./chroma_vector_store", **kwargs):
        """Initialize the ChromaDB client with telemetry disabled.

        Args:
            store_dir: Directory path where ChromaDB data is persisted.
            **kwargs: Additional keyword arguments passed to LocalVectorStore.
        """
        super().__init__(store_dir=store_dir, **kwargs)
        self.collections: dict = {}
        # Disable telemetry to avoid PostHog warnings
        # Use PersistentClient explicitly to avoid singleton conflicts
        from chromadb import PersistentClient, ClientAPI
        from chromadb.config import Settings

        self._client: ClientAPI = PersistentClient(
            path=self.store_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        logger.info(f"ChromaDB client initialized with store_dir={self.store_dir}")

    def _get_collection(self, workspace_id: str):
        """Get or create a ChromaDB collection for the given workspace.

        Args:
            workspace_id: The workspace identifier.

        Returns:
            ChromaDB Collection object for the workspace.
        """
        if workspace_id not in self.collections:
            self.collections[workspace_id] = self._client.get_or_create_collection(workspace_id)
        return self.collections[workspace_id]

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a workspace exists in the vector store.

        Args:
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            True if the workspace exists, False otherwise.
        """
        return workspace_id in [c.name for c in self._client.list_collections()]

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a workspace from the vector store.

        Args:
            workspace_id: The workspace identifier to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        self._client.delete_collection(workspace_id)
        if workspace_id in self.collections:
            del self.collections[workspace_id]

    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new workspace in the vector store.

        Args:
            workspace_id: The workspace identifier to create.
            **kwargs: Additional keyword arguments (unused).
        """
        self.collections[workspace_id] = self._client.get_or_create_collection(workspace_id)

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces (collections) in ChromaDB.

        Returns:
            List[str]: Workspace identifiers (collection names).
        """
        return [c.name for c in self._client.list_collections()]

    def iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace.

        Args:
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).

        Yields:
            VectorNode objects from the workspace.
        """
        collection = self._get_collection(workspace_id)
        results = collection.get()
        for i in range(len(results["ids"])):
            node = VectorNode(
                workspace_id=workspace_id,
                unique_id=results["ids"][i],
                content=results["documents"][i],
                metadata=results["metadatas"][i],
            )
            yield node

    @staticmethod
    def _build_chroma_filters(filter_dict: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Build ChromaDB where clause from filter_dict.

        Converts a filter dictionary into ChromaDB's where clause format.
        Supports both term filters (exact match) and range filters (gte, lte, gt, lt).

        Args:
            filter_dict: Dictionary of filters to apply. Can contain:
                - Term filters: {"key": "value"} -> exact match
                - Range filters: {"key": {"gte": 1, "lte": 10}} -> range query

        Returns:
            ChromaDB where clause dictionary, or None if no filters provided.
        """
        if not filter_dict:
            return None

        where_conditions = {}
        for key, filter_value in filter_dict.items():
            if isinstance(filter_value, dict):
                # Range filter: {"gte": 1, "lte": 10}
                range_conditions = {}
                if "gte" in filter_value:
                    range_conditions["$gte"] = filter_value["gte"]
                if "lte" in filter_value:
                    range_conditions["$lte"] = filter_value["lte"]
                if "gt" in filter_value:
                    range_conditions["$gt"] = filter_value["gt"]
                if "lt" in filter_value:
                    range_conditions["$lt"] = filter_value["lt"]
                if range_conditions:
                    where_conditions[key] = range_conditions
            else:
                # Term filter: direct value comparison
                where_conditions[key] = filter_value

        return where_conditions if where_conditions else None

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes in the workspace.

        Args:
            query: Text query to search for.
            workspace_id: The workspace identifier.
            top_k: Number of top results to return (default: 1).
            filter_dict: Optional metadata filters to apply.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List of VectorNode objects matching the query, ordered by similarity.
            Returns empty list if workspace doesn't exist.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        collection = self._get_collection(workspace_id)
        query_vector = self.embedding_model.get_embeddings(query)

        # Build where clause from filter_dict
        where_clause = self._build_chroma_filters(filter_dict)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where_clause,
        )

        nodes = []
        for i in range(len(results["ids"][0])):
            node = VectorNode(
                workspace_id=workspace_id,
                unique_id=results["ids"][0][i],
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
            )
            # ChromaDB returns distances, convert to similarity score
            if results.get("distances") and len(results["distances"][0]) > i:
                distance = results["distances"][0][i]
                # Convert distance to similarity (assuming cosine distance)
                node.metadata["score"] = 1.0 - distance
            nodes.append(node)

        return nodes

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Insert vector nodes into the workspace.

        If nodes don't have embeddings, they will be generated using the embedding model.
        Creates the workspace if it doesn't exist.

        Args:
            nodes: Single VectorNode or list of VectorNode objects to insert.
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]
        now_embedded_nodes = self.embedding_model.get_node_embeddings(not_embedded_nodes)
        all_nodes = embedded_nodes + now_embedded_nodes

        collection = self._get_collection(workspace_id)
        collection.add(
            ids=[n.unique_id for n in all_nodes],
            embeddings=[n.vector for n in all_nodes],
            documents=[n.content for n in all_nodes],
            metadatas=[n.metadata for n in all_nodes],
        )

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Delete vector nodes from the workspace.

        Args:
            node_ids: Single node ID or list of node IDs to delete.
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        collection = self._get_collection(workspace_id)
        collection.delete(ids=node_ids)

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Async version of search using async embedding and run_in_executor for ChromaDB operations.

        Args:
            query: Text query to search for.
            workspace_id: The workspace identifier.
            top_k: Number of top results to return (default: 1).
            filter_dict: Optional metadata filters to apply.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List of VectorNode objects matching the query, ordered by similarity.
            Returns empty list if workspace doesn't exist.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Use async embedding
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # Build where clause from filter_dict
        where_clause = self._build_chroma_filters(filter_dict)

        # Execute ChromaDB query in thread pool
        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(C.thread_pool, self._get_collection, workspace_id)
        results = await loop.run_in_executor(
            C.thread_pool,
            partial(collection.query, query_embeddings=[query_vector], n_results=top_k, where=where_clause),
        )

        nodes = []
        for i in range(len(results["ids"][0])):
            node = VectorNode(
                workspace_id=workspace_id,
                unique_id=results["ids"][0][i],
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
            )
            # ChromaDB returns distances, convert to similarity score
            if results.get("distances") and len(results["distances"][0]) > i:
                distance = results["distances"][0][i]
                # Convert distance to similarity (assuming cosine distance)
                node.metadata["score"] = 1.0 - distance
            nodes.append(node)

        return nodes

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert using async embedding and run_in_executor for ChromaDB operations.

        If nodes don't have embeddings, they will be generated using the async embedding model.
        Creates the workspace if it doesn't exist.

        Args:
            nodes: Single VectorNode or list of VectorNode objects to insert.
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]

        # Use async embedding
        now_embedded_nodes = await self.embedding_model.get_node_embeddings_async(not_embedded_nodes)

        all_nodes = embedded_nodes + now_embedded_nodes

        # Execute ChromaDB operations in thread pool
        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(C.thread_pool, self._get_collection, workspace_id)
        await loop.run_in_executor(
            C.thread_pool,
            partial(
                collection.add,
                ids=[n.unique_id for n in all_nodes],
                embeddings=[n.vector for n in all_nodes],
                documents=[n.content for n in all_nodes],
                metadatas=[n.metadata for n in all_nodes],
            ),
        )

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete using run_in_executor for ChromaDB operations.

        Args:
            node_ids: Single node ID or list of node IDs to delete.
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        # Execute ChromaDB operations in thread pool
        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(C.thread_pool, self._get_collection, workspace_id)
        await loop.run_in_executor(C.thread_pool, partial(collection.delete, ids=node_ids))
