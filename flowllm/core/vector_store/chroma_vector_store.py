"""
ChromaDB vector store implementation.

This module provides a ChromaDB-based vector store that stores vector nodes
in ChromaDB collections. It supports workspace management, vector similarity search,
metadata filtering, and provides both synchronous and asynchronous operations.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger

from .memory_vector_store import MemoryVectorStore
from ..context import C
from ..schema import VectorNode

# Disable ChromaDB telemetry to avoid PostHog warnings
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")


@C.register_vector_store("chroma")
class ChromaVectorStore(MemoryVectorStore):
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

    # ==================== Initialization ====================

    def __init__(self, store_dir: str = "./chroma_vector_store", **kwargs):
        """Initialize the ChromaDB client with telemetry disabled.

        Args:
            store_dir: Directory path where ChromaDB data is persisted.
            **kwargs: Additional keyword arguments passed to MemoryVectorStore.
        """
        super().__init__(**kwargs)
        self.store_dir = store_dir
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

    @property
    def store_path(self) -> Path:
        """
        Get the storage directory path.

        Returns:
            Path object representing the storage directory.
        """
        return Path(self.store_dir)

    # ==================== Static Helper Methods ====================

    @staticmethod
    def _build_chroma_filters(
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> tuple[Optional[Dict], Optional[List[str]]]:
        """Build ChromaDB where clause from filter_dict.

        Converts a filter dictionary into ChromaDB's where clause format.
        Supports both term filters (exact match) and range filters (gte, lte, gt, lt).
        Handles unique_id specially since it's stored as ChromaDB's document ID.

        Args:
            filter_dict: Dictionary of filters to apply. Can contain:
                - Term filters: {"key": "value"} -> exact match
                - Range filters: {"key": {"gte": 1, "lte": 10}} -> range query
                - unique_id: Filters by document ID (stored separately from metadata)
                - Keys can use "metadata." prefix (will be stripped for ChromaDB)

        Returns:
            Tuple of (where_clause, ids_filter):
                - where_clause: ChromaDB where clause dictionary for metadata filters, or None
                - ids_filter: List of document IDs to filter by, or None
        """
        if not filter_dict:
            return None, None

        where_conditions = {}
        ids_filter = None

        for key, filter_value in filter_dict.items():
            # Handle unique_id specially - it's stored as ChromaDB's document ID
            if key == "unique_id":
                if isinstance(filter_value, list):
                    ids_filter = filter_value
                else:
                    ids_filter = [filter_value]
                continue

            # Strip "metadata." prefix if present (ChromaDB stores metadata fields directly)
            if key.startswith("metadata."):
                chroma_key = key[len("metadata.") :]
            else:
                chroma_key = key

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
                    where_conditions[chroma_key] = range_conditions
            elif isinstance(filter_value, list):
                # List filter: use $in operator for OR logic
                where_conditions[chroma_key] = {"$in": filter_value}
            else:
                # Term filter: direct value comparison
                where_conditions[chroma_key] = filter_value

        return (where_conditions if where_conditions else None, ids_filter)

    # ==================== Private Helper Methods ====================

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

    # ==================== Workspace Management Methods ====================

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a workspace exists in the vector store.

        Args:
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            True if the workspace exists, False otherwise.
        """
        # Check cache first for better performance
        if workspace_id in self.collections:
            return True
        # Fall back to checking the client
        try:
            self._client.get_collection(workspace_id)
            return True
        except Exception:
            return False

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace.

        Args:
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            True if the workspace exists, False otherwise.
        """
        return await self._run_sync_in_executor(self.exist_workspace, workspace_id, **kwargs)

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a workspace from the vector store.

        Args:
            workspace_id: The workspace identifier to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        if self.exist_workspace(workspace_id):
            self._client.delete_collection(workspace_id)
            if workspace_id in self.collections:
                del self.collections[workspace_id]
            logger.info(f"Deleted workspace_id={workspace_id} from ChromaDB")

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Async version of delete_workspace.

        Args:
            workspace_id: The workspace identifier to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        return await self._run_sync_in_executor(self.delete_workspace, workspace_id, **kwargs)

    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new workspace in the vector store.

        Args:
            workspace_id: The workspace identifier to create.
            **kwargs: Additional keyword arguments (unused).
        """
        self.collections[workspace_id] = self._client.get_or_create_collection(workspace_id)
        logger.info(f"Created workspace_id={workspace_id} in ChromaDB")

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Async version of create_workspace.

        Args:
            workspace_id: The workspace identifier to create.
            **kwargs: Additional keyword arguments (unused).
        """
        return await self._run_sync_in_executor(self.create_workspace, workspace_id, **kwargs)

    def list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """List all nodes in a workspace.

        Args:
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List of VectorNode objects from the workspace.
        """
        if not self.exist_workspace(workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        collection = self._get_collection(workspace_id)
        results = collection.get(include=["documents", "metadatas", "embeddings"])

        nodes = []
        documents = results.get("documents")
        metadatas = results.get("metadatas")
        embeddings = results.get("embeddings")
        for i in range(len(results["ids"])):
            node = VectorNode(
                workspace_id=workspace_id,
                unique_id=results["ids"][i],
                content=documents[i] if documents is not None else "",
                metadata=metadatas[i] if metadatas is not None else {},
                vector=embeddings[i] if embeddings is not None else None,
            )
            nodes.append(node)
        return nodes

    async def async_list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """Async version of list_workspace_nodes.

        Args:
            workspace_id: The workspace identifier.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List of VectorNode objects from the workspace.
        """
        return await self._run_sync_in_executor(self.list_workspace_nodes, workspace_id, **kwargs)

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Export a workspace from ChromaDB to disk at the specified path.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist or path is empty.
        """
        if not self.exist_workspace(workspace_id):
            logger.warning(f"workspace_id={workspace_id} not found in ChromaDB!")
            return {}

        if not path:
            logger.warning("path is empty, cannot dump workspace!")
            return {}

        nodes = self.list_workspace_nodes(workspace_id, **kwargs)

        return self._dump_to_path(
            nodes=nodes,
            workspace_id=workspace_id,
            path=path,
            callback_fn=callback_fn,
            **kwargs,
        )

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Async version of dump_workspace.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist or path is empty.
        """
        return await self._run_sync_in_executor(
            self.dump_workspace,
            workspace_id,
            path,
            callback_fn,
            **kwargs,
        )

    def load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: Optional[List[VectorNode]] = None,
        callback_fn=None,
        **kwargs,
    ):
        """Load a workspace into ChromaDB from disk, optionally merging with provided nodes.

        This method replaces any existing workspace with the same ID,
        then loads nodes from the specified path and/or the provided nodes list.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
                  If empty, only loads from nodes parameter.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        if self.exist_workspace(workspace_id):
            self.delete_workspace(workspace_id=workspace_id, **kwargs)
            logger.info(f"Cleared existing workspace_id={workspace_id} from ChromaDB")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        if path:
            all_nodes.extend(
                self._load_from_path(
                    path=path,
                    workspace_id=workspace_id,
                    callback_fn=callback_fn,
                    **kwargs,
                ),
            )

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)

        logger.info(f"Loaded workspace_id={workspace_id} with {len(all_nodes)} nodes into ChromaDB")
        return {"size": len(all_nodes)}

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: Optional[List[VectorNode]] = None,
        callback_fn=None,
        **kwargs,
    ):
        """Async version of load_workspace.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
                  If empty, only loads from nodes parameter.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        return await self._run_sync_in_executor(
            self.load_workspace,
            workspace_id,
            path,
            nodes,
            callback_fn,
            **kwargs,
        )

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Copy all nodes from one workspace to another in ChromaDB.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
        if not self.exist_workspace(src_workspace_id):
            logger.warning(f"src_workspace_id={src_workspace_id} not found in ChromaDB!")
            return {}

        if not self.exist_workspace(dest_workspace_id):
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = self.list_workspace_nodes(src_workspace_id, **kwargs)
        node_size = len(src_nodes)

        new_nodes = []
        for node in src_nodes:
            new_node = VectorNode(**node.model_dump())
            new_node.workspace_id = dest_workspace_id
            new_nodes.append(new_node)

        if new_nodes:
            self.insert(nodes=new_nodes, workspace_id=dest_workspace_id, **kwargs)

        logger.info(f"Copied {node_size} nodes from {src_workspace_id} to {dest_workspace_id}")
        return {"size": node_size}

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Async version of copy_workspace.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
        return await self._run_sync_in_executor(
            self.copy_workspace,
            src_workspace_id,
            dest_workspace_id,
            **kwargs,
        )

    def list_workspace(self, **kwargs) -> List[str]:
        """List all existing workspaces (collections) in ChromaDB.

        Returns:
            List[str]: Workspace identifiers (collection names).
        """
        return [c.name for c in self._client.list_collections()]

    async def async_list_workspace(self, **kwargs) -> List[str]:
        """Async version of list_workspace.

        Returns:
            List[str]: Workspace identifiers (collection names).
        """
        return await self._run_sync_in_executor(self.list_workspace, **kwargs)

    # ==================== Search Methods ====================

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes in the workspace.

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
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

        # Build where clause and ids filter from filter_dict
        where_clause, ids_filter = self._build_chroma_filters(filter_dict)

        # When query is empty, degrade to filter-only search
        use_vector_search = bool(query)

        if use_vector_search:
            query_vector = self.get_embeddings(query)
            query_kwargs = {
                "query_embeddings": [query_vector],
                "n_results": top_k,
            }
            if where_clause:
                query_kwargs["where"] = where_clause
            if ids_filter:
                query_kwargs["ids"] = ids_filter
            results = collection.query(**query_kwargs)
        else:
            # Filter-only search without vector similarity
            get_kwargs = {
                "limit": top_k,
                "include": ["documents", "metadatas"],
            }
            if where_clause:
                get_kwargs["where"] = where_clause
            if ids_filter:
                get_kwargs["ids"] = ids_filter
            results = collection.get(**get_kwargs)
            # Normalize results format to match query results
            results = {
                "ids": [results["ids"]],
                "documents": [results["documents"]],
                "metadatas": [results["metadatas"]],
                "distances": None,
            }

        nodes = []
        for i in range(len(results["ids"][0])):
            node = VectorNode(
                workspace_id=workspace_id,
                unique_id=results["ids"][0][i],
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
            )
            # ChromaDB returns distances, convert to similarity score
            # Note: ChromaDB uses L2 (Euclidean) distance by default, but also supports
            # cosine and inner product. Using 1 / (1 + distance) normalizes to [0, 1]
            # and works for both L2 and cosine distance metrics.
            if use_vector_search and results.get("distances") and len(results["distances"][0]) > i:
                distance = results["distances"][0][i]
                node.metadata["score"] = 1.0 / (1.0 + distance)
            nodes.append(node)

        return nodes

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Async version of search using async embedding and run_in_executor for ChromaDB operations.

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
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

        # Build where clause and ids filter from filter_dict
        where_clause, ids_filter = self._build_chroma_filters(filter_dict)

        # When query is empty, degrade to filter-only search
        use_vector_search = bool(query)

        if use_vector_search:
            # Use async embedding
            query_vector = await self.async_get_embeddings(query)

            # Execute ChromaDB query in thread pool
            def _do_query():
                collection = self._get_collection(workspace_id)
                query_kwargs = {
                    "query_embeddings": [query_vector],
                    "n_results": top_k,
                }
                if where_clause:
                    query_kwargs["where"] = where_clause
                if ids_filter:
                    query_kwargs["ids"] = ids_filter
                return collection.query(**query_kwargs)

            results = await self._run_sync_in_executor(_do_query)
        else:
            # Filter-only search without vector similarity

            def _do_get():
                collection = self._get_collection(workspace_id)
                get_kwargs = {
                    "limit": top_k,
                    "include": ["documents", "metadatas"],
                }
                if where_clause:
                    get_kwargs["where"] = where_clause
                if ids_filter:
                    get_kwargs["ids"] = ids_filter
                return collection.get(**get_kwargs)

            get_results = await self._run_sync_in_executor(_do_get)
            # Normalize results format to match query results
            results = {
                "ids": [get_results["ids"]],
                "documents": [get_results["documents"]],
                "metadatas": [get_results["metadatas"]],
                "distances": None,
            }

        nodes = []
        for i in range(len(results["ids"][0])):
            node = VectorNode(
                workspace_id=workspace_id,
                unique_id=results["ids"][0][i],
                content=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
            )
            # ChromaDB returns distances, convert to similarity score
            # Note: ChromaDB uses L2 (Euclidean) distance by default, but also supports
            # cosine and inner product. Using 1 / (1 + distance) normalizes to [0, 1]
            # and works for both L2 and cosine distance metrics.
            if use_vector_search and results.get("distances") and len(results["distances"][0]) > i:
                distance = results["distances"][0][i]
                node.metadata["score"] = 1.0 / (1.0 + distance)
            nodes.append(node)

        return nodes

    # ==================== Insert Methods ====================

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

        # Generate embeddings for nodes that don't have them
        all_nodes = self.get_node_embeddings(nodes)

        collection = self._get_collection(workspace_id)

        # Check for existing nodes and use upsert logic
        existing_ids = set(collection.get()["ids"])
        update_cnt = sum(1 for n in all_nodes if n.unique_id in existing_ids)

        collection.upsert(
            ids=[n.unique_id for n in all_nodes],
            embeddings=[n.vector for n in all_nodes],
            documents=[n.content for n in all_nodes],
            metadatas=[n.metadata for n in all_nodes],
        )

        total_nodes = collection.count()
        logger.info(
            f"Inserted into workspace_id={workspace_id} nodes.size={len(all_nodes)} "
            f"total.size={total_nodes} update_cnt={update_cnt}",
        )

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

        # Use async embedding
        all_nodes = await self.async_get_node_embeddings(nodes)

        # Execute ChromaDB operations in thread pool
        def _do_insert():
            collection = self._get_collection(workspace_id)
            existing_ids = set(collection.get()["ids"])
            update_cnt = sum(1 for n in all_nodes if n.unique_id in existing_ids)

            collection.upsert(
                ids=[n.unique_id for n in all_nodes],
                embeddings=[n.vector for n in all_nodes],
                documents=[n.content for n in all_nodes],
                metadatas=[n.metadata for n in all_nodes],
            )
            return collection.count(), update_cnt

        total_nodes, update_cnt = await self._run_sync_in_executor(_do_insert)

        logger.info(
            f"Async inserted into workspace_id={workspace_id} nodes.size={len(all_nodes)} "
            f"total.size={total_nodes} update_cnt={update_cnt}",
        )

    # ==================== Delete Methods ====================

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
        before_size = collection.count()
        collection.delete(ids=node_ids)
        after_size = collection.count()

        logger.info(
            f"Deleted from workspace_id={workspace_id} before_size={before_size} "
            f"after_size={after_size} deleted_cnt={before_size - after_size}",
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
        def _do_delete():
            collection = self._get_collection(workspace_id)
            before_size = collection.count()
            collection.delete(ids=node_ids)
            after_size = collection.count()
            return before_size, after_size

        before_size, after_size = await self._run_sync_in_executor(_do_delete)

        logger.info(
            f"Deleted from workspace_id={workspace_id} before_size={before_size} "
            f"after_size={after_size} deleted_cnt={before_size - after_size}",
        )

    # ==================== Close Methods ====================

    def close(self):
        """
        Close the vector store and clean up resources.

        For ChromaVectorStore, this clears the collections cache.
        ChromaDB handles its own persistence.
        """
        self.collections.clear()

    async def async_close(self):
        """
        Async version of close.

        For ChromaVectorStore, this clears the collections cache.
        """
        self.close()
