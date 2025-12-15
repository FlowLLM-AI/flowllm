"""Qdrant vector store implementation.

This module provides a Qdrant-based vector store that uses Qdrant for storing
and searching vector embeddings. Qdrant is an open-source vector similarity
search engine that provides high-performance vector search capabilities.

The implementation supports both synchronous and asynchronous operations, and
provides native Qdrant async client support for better async performance.
"""

import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger

from .memory_vector_store import MemoryVectorStore
from ..context import C
from ..schema import VectorNode


@C.register_vector_store("qdrant")
class QdrantVectorStore(MemoryVectorStore):
    """Qdrant-based vector store implementation.

    This class provides a vector store implementation using Qdrant as the
    underlying storage engine. It supports workspace management, vector similarity
    search with filtering, and provides both synchronous and asynchronous operations.

    The QdrantVectorStore can be configured to connect to:
    - A local Qdrant instance (default: localhost:6333)
    - A remote Qdrant instance via URL
    - Qdrant Cloud via URL and API key

    Attributes:
        url: Optional URL for connecting to Qdrant. If provided, host and port
            are ignored. Useful for Qdrant Cloud or custom deployments.
        host: Host address of the Qdrant server (default: localhost).
        port: Port number of the Qdrant server (default: 6333).
        api_key: Optional API key for authentication (required for Qdrant Cloud).
        distance: Distance metric for vector similarity (default: COSINE).
            Can be COSINE, EUCLIDEAN, or DOT.
        _client: Private QdrantClient instance for synchronous operations.
        _async_client: Private AsyncQdrantClient instance for asynchronous operations.
    """

    # ==================== Initialization ====================

    def __init__(
        self,
        url: str | None = None,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
        distance: str | None = None,
        **kwargs,
    ):
        """Initialize Qdrant clients.

        Args:
            url: Optional URL for connecting to Qdrant. If provided, host and port are ignored.
            host: Host address of the Qdrant server (default: localhost from env or "localhost").
            port: Port number of the Qdrant server (default: 6333 from env or 6333).
            api_key: Optional API key for authentication (required for Qdrant Cloud).
            distance: Distance metric for vector similarity (default: COSINE).
            **kwargs: Additional keyword arguments passed to MemoryVectorStore.
        """
        super().__init__(**kwargs)
        self.url = url
        self.host = host or os.getenv("FLOW_QDRANT_HOST", "localhost")
        self.port = port or int(os.getenv("FLOW_QDRANT_PORT", "6333"))
        self.api_key = api_key

        # Set default distance to COSINE if not set
        from qdrant_client.http.models import Distance

        if distance is None:
            self.distance: Distance = Distance.COSINE
        else:
            self.distance: Distance = Distance(distance)

        # Build kwargs for QdrantClient initialization
        client_kwargs = {}
        if self.url is not None:
            client_kwargs["url"] = self.url
        else:
            if self.host is not None:
                client_kwargs["host"] = self.host
            if self.port is not None:
                client_kwargs["port"] = self.port

        if self.api_key is not None:
            client_kwargs["api_key"] = self.api_key

        from qdrant_client import QdrantClient, AsyncQdrantClient

        self._client = QdrantClient(**client_kwargs)
        self._async_client = AsyncQdrantClient(**client_kwargs)

        # Log connection info
        if self.url:
            logger.info(f"Qdrant client initialized with url={self.url}")
        else:
            logger.info(f"Qdrant client initialized with host={self.host} port={self.port}")

    # ==================== Static Helper Methods ====================

    @staticmethod
    def _convert_id_to_uuid(node_id: str) -> str:
        """Convert a string ID to a UUID string.

        Uses UUID v5 with a fixed namespace to ensure deterministic conversion.
        If the input is already a valid UUID, returns it as-is.

        Args:
            node_id: The node ID to convert.

        Returns:
            A valid UUID string.
        """
        try:
            # Check if it's already a valid UUID
            uuid.UUID(node_id)
            return node_id
        except (ValueError, AttributeError):
            # Convert string to UUID v5 using a fixed namespace
            # Using DNS namespace as a standard base
            return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(node_id)))

    @staticmethod
    def point2node(point, workspace_id: str) -> VectorNode:
        """Convert Qdrant point to VectorNode.

        Converts a Qdrant Record object (returned from search or scroll operations)
        into a VectorNode object, extracting the ID, vector, content, and metadata.

        Args:
            point: The Qdrant Record object containing point data.
            workspace_id: The workspace ID to assign to the VectorNode.

        Returns:
            VectorNode: A VectorNode object created from the Qdrant point data.
        """
        # Use original_id if available, otherwise use the point ID
        original_id = point.payload.get("original_id", str(point.id))
        node = VectorNode(
            unique_id=original_id,
            workspace_id=workspace_id,
            content=point.payload.get("content", ""),
            metadata=point.payload.get("metadata", {}),
            vector=point.vector,
        )
        if hasattr(point, "score") and point.score is not None:
            node.metadata["score"] = point.score
        return node

    @staticmethod
    def _build_qdrant_filters(filter_dict: Optional[Dict[str, Any]] = None):
        """Build Qdrant filter from filter_dict.

        Converts a filter dictionary into a Qdrant Filter object. Supports:
        - Term filters: Direct value matching (e.g., {"node_type": "n1"})
        - Range filters: Numeric range queries (e.g., {"age": {"gte": 18, "lte": 65}})

        Args:
            filter_dict: Optional dictionary of filters. Keys are field names (automatically
                prefixed with "metadata." if not already present). Values can be:
                - Direct values for term matching
                - Dict with range operators: "gte", "lte", "gt", "lt"

        Returns:
            Optional Filter object for Qdrant queries, or None if filter_dict is empty.

        Example:
            ```python
            # Term filter
            filter_dict = {"node_type": "n1"}

            # Range filter
            filter_dict = {"age": {"gte": 18, "lte": 65}}
            ```
        """
        from qdrant_client.http.models import FieldCondition, MatchAny, MatchValue, Range

        if not filter_dict:
            return None

        conditions = []
        for key, filter_value in filter_dict.items():
            # Handle special keys that are stored at payload root level
            if key == "unique_id":
                qdrant_key = "original_id"
            # Handle nested keys by prefixing with metadata.
            elif not key.startswith("metadata."):
                qdrant_key = f"metadata.{key}"
            else:
                qdrant_key = key

            if isinstance(filter_value, dict):
                # Range filter: {"gte": 1, "lte": 10}
                range_conditions = {}
                if "gte" in filter_value:
                    range_conditions["gte"] = filter_value["gte"]
                if "lte" in filter_value:
                    range_conditions["lte"] = filter_value["lte"]
                if "gt" in filter_value:
                    range_conditions["gt"] = filter_value["gt"]
                if "lt" in filter_value:
                    range_conditions["lt"] = filter_value["lt"]
                if range_conditions:
                    conditions.append(
                        FieldCondition(
                            key=qdrant_key,
                            range=Range(**range_conditions),
                        ),
                    )
            elif isinstance(filter_value, list):
                # List filter: use MatchAny for OR logic
                conditions.append(
                    FieldCondition(
                        key=qdrant_key,
                        match=MatchAny(any=filter_value),
                    ),
                )
            else:
                # Term filter: direct value comparison
                conditions.append(
                    FieldCondition(
                        key=qdrant_key,
                        match=MatchValue(value=filter_value),
                    ),
                )

        if not conditions:
            return None

        from qdrant_client.http.models import Filter

        return Filter(must=conditions)

    # ==================== Workspace Management Methods ====================

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a collection exists in Qdrant.

        Args:
            workspace_id: The ID of the workspace (collection) to check.
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            True if the collection exists, False otherwise.
        """
        return self._client.collection_exists(collection_name=workspace_id)

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace using native Qdrant async client.

        Args:
            workspace_id: The ID of the workspace (collection) to check.
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            True if the collection exists, False otherwise.
        """
        return await self._async_client.collection_exists(collection_name=workspace_id)

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a collection from Qdrant.

        Args:
            workspace_id: The ID of the workspace (collection) to delete.
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            The result of the delete_collection operation.
        """
        return self._client.delete_collection(collection_name=workspace_id)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Async version of delete_workspace using native Qdrant async client.

        Args:
            workspace_id: The ID of the workspace (collection) to delete.
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            The result of the delete_collection operation.
        """
        return await self._async_client.delete_collection(collection_name=workspace_id)

    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new collection in Qdrant.

        Creates a new collection with vector configuration based on the embedding
        model's dimensions and the configured distance metric.

        Args:
            workspace_id: The ID of the workspace (collection) to create.
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            The result of the create_collection operation.
        """
        from qdrant_client.http.models import VectorParams

        return self._client.create_collection(
            collection_name=workspace_id,
            vectors_config=VectorParams(
                size=self.embedding_model.dimensions,
                distance=self.distance,
            ),
        )

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Async version of create_workspace using native Qdrant async client.

        Creates a new collection with vector configuration based on the embedding
        model's dimensions and the configured distance metric.

        Args:
            workspace_id: The ID of the workspace (collection) to create.
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            The result of the create_collection operation.
        """
        from qdrant_client.http.models import VectorParams

        return await self._async_client.create_collection(
            collection_name=workspace_id,
            vectors_config=VectorParams(
                size=self.embedding_model.dimensions,
                distance=self.distance,
            ),
        )

    def list_workspace_nodes(
        self,
        workspace_id: str,
        limit: int = 10000,
        **kwargs,
    ) -> List[VectorNode]:
        """List all nodes in a workspace.

        Uses Qdrant's scroll API to paginate through all points in a collection,
        converting them to VectorNode objects.

        Args:
            workspace_id: The ID of the workspace to list nodes from.
            limit: Maximum number of points to retrieve per scroll operation (default: 10000).
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            List[VectorNode]: All nodes in the workspace.
        """
        nodes: List[VectorNode] = []
        offset = None
        while True:
            records, next_offset = self._client.scroll(
                collection_name=workspace_id,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )

            if not records:
                break

            for record in records:
                node = self.point2node(record, workspace_id)
                nodes.append(node)

            if next_offset is None:
                break
            offset = next_offset

        return nodes

    async def async_list_workspace_nodes(
        self,
        workspace_id: str,
        limit: int = 10000,
        **kwargs,
    ) -> List[VectorNode]:
        """Async version of list_workspace_nodes using native Qdrant async client.

        Uses Qdrant's async scroll API to paginate through all points in a collection,
        converting them to VectorNode objects.

        Args:
            workspace_id: The ID of the workspace to iterate nodes from.
            limit: Maximum number of points to retrieve per scroll operation (default: 10000).
            **kwargs: Additional keyword arguments (unused, kept for interface compatibility).

        Returns:
            List[VectorNode]: All nodes in the workspace.
        """
        nodes: List[VectorNode] = []
        offset = None
        while True:
            records, next_offset = await self._async_client.scroll(
                collection_name=workspace_id,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )

            if not records:
                break

            for record in records:
                node = self.point2node(record, workspace_id)
                nodes.append(node)

            if next_offset is None:
                break
            offset = next_offset

        return nodes

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces (collections) in Qdrant.

        Returns:
            List[str]: Workspace identifiers (collection names).
        """
        return [c.name for c in self._client.get_collections().collections]

    async def async_list_workspace(self, **kwargs) -> List[str]:
        """
        Async version of list_workspace using native Qdrant async client.

        Returns:
            List[str]: Workspace identifiers (collection names).
        """
        collections = await self._async_client.get_collections()
        return [c.name for c in collections.collections]

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Export a workspace to disk at the specified path.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist.
        """
        if not self.exist_workspace(workspace_id=workspace_id, **kwargs):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return {}

        return self._dump_to_path(
            nodes=self.list_workspace_nodes(workspace_id=workspace_id, **kwargs),
            workspace_id=workspace_id,
            path=path,
            callback_fn=callback_fn,
            **kwargs,
        )

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Export a workspace to disk at the specified path (async).

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id, **kwargs):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return {}

        nodes = await self.async_list_workspace_nodes(workspace_id=workspace_id, **kwargs)
        return await self._run_sync_in_executor(
            self._dump_to_path,
            nodes=nodes,
            workspace_id=workspace_id,
            path=path,
            callback_fn=callback_fn,
            **kwargs,
        )

    def load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] | None = None,
        callback_fn=None,
        **kwargs,
    ):
        """Load a workspace from disk, optionally merging with provided nodes.

        This method replaces any existing workspace with the same ID, then loads
        nodes from the specified path and/or the provided nodes list.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        if self.exist_workspace(workspace_id, **kwargs):
            self.delete_workspace(workspace_id=workspace_id, **kwargs)
            logger.info(f"delete workspace_id={workspace_id}")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        all_nodes.extend(self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs))

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)
        return {"size": len(all_nodes)}

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] | None = None,
        callback_fn=None,
        **kwargs,
    ):
        """Load a workspace from disk, optionally merging with provided nodes (async).

        This method replaces any existing workspace with the same ID, then loads
        nodes from the specified path and/or the provided nodes list.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        if await self.async_exist_workspace(workspace_id, **kwargs):
            await self.async_delete_workspace(workspace_id=workspace_id, **kwargs)
            logger.info(f"delete workspace_id={workspace_id}")

        await self.async_create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        if path:
            loaded_nodes = await self._run_sync_in_executor(
                lambda: list(
                    self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs),
                ),
            )
            all_nodes.extend(loaded_nodes)

        if all_nodes:
            await self.async_insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)
        return {"size": len(all_nodes)}

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Copy all nodes from one workspace to another.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
        if not self.exist_workspace(workspace_id=src_workspace_id, **kwargs):
            logger.warning(f"src_workspace_id={src_workspace_id} does not exist!")
            return {}

        if not self.exist_workspace(dest_workspace_id, **kwargs):
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = self.list_workspace_nodes(workspace_id=src_workspace_id, **kwargs)
        if src_nodes:
            self.insert(nodes=src_nodes, workspace_id=dest_workspace_id, **kwargs)

        return {"size": len(src_nodes)}

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Copy all nodes from one workspace to another (async).

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
        if not await self.async_exist_workspace(workspace_id=src_workspace_id, **kwargs):
            logger.warning(f"src_workspace_id={src_workspace_id} does not exist!")
            return {}

        if not await self.async_exist_workspace(dest_workspace_id, **kwargs):
            await self.async_create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = await self.async_list_workspace_nodes(workspace_id=src_workspace_id, **kwargs)
        if src_nodes:
            await self.async_insert(nodes=src_nodes, workspace_id=dest_workspace_id, **kwargs)

        return {"size": len(src_nodes)}

    # ==================== Search Methods ====================

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
        filter-only search without vector similarity ranking.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: The ID of the workspace to search in.
            top_k: Number of most similar results to return (default: 1).
            filter_dict: Optional dictionary of filters to apply to the search.
                See _build_qdrant_filters for filter format details.
            **kwargs: Additional keyword arguments passed to Qdrant's query_points method.

        Returns:
            List[VectorNode]: List of matching nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a
                "score" key in metadata. When query is empty, nodes are returned
                in storage order without scores.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Build filters from filter_dict
        qdrant_filter = self._build_qdrant_filters(filter_dict)

        # When query is empty, degrade to filter-only search without vector similarity
        use_vector_search = bool(query)

        if use_vector_search:
            query_vector = self.get_embeddings(query)

            response = self._client.query_points(
                collection_name=workspace_id,
                query=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=True,
                **kwargs,
            )

            nodes: List[VectorNode] = []
            for scored_point in response.points:
                node = self.point2node(scored_point, workspace_id)
                node.metadata["score"] = scored_point.score
                nodes.append(node)

            return nodes
        else:
            # Filter-only search using scroll API
            records, _ = self._client.scroll(
                collection_name=workspace_id,
                limit=top_k,
                scroll_filter=qdrant_filter,
                with_payload=True,
                with_vectors=True,
            )

            nodes: List[VectorNode] = []
            for record in records:
                node = self.point2node(record, workspace_id)
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
        """Async version of search using native Qdrant async client and async embedding.

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: The ID of the workspace to search in.
            top_k: Number of most similar results to return (default: 1).
            filter_dict: Optional dictionary of filters to apply to the search.
                See _build_qdrant_filters for filter format details.
            **kwargs: Additional keyword arguments passed to Qdrant's async query_points method.

        Returns:
            List[VectorNode]: List of matching nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a
                "score" key in metadata. When query is empty, nodes are returned
                in storage order without scores.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Build filters from filter_dict
        qdrant_filter = self._build_qdrant_filters(filter_dict)

        # When query is empty, degrade to filter-only search without vector similarity
        use_vector_search = bool(query)

        if use_vector_search:
            # Use async embedding
            query_vector = await self.async_get_embeddings(query)

            response = await self._async_client.query_points(
                collection_name=workspace_id,
                query=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=True,
                **kwargs,
            )

            nodes: List[VectorNode] = []
            for scored_point in response.points:
                node = self.point2node(scored_point, workspace_id)
                node.metadata["score"] = scored_point.score
                nodes.append(node)

            return nodes
        else:
            # Filter-only search using scroll API
            records, _ = await self._async_client.scroll(
                collection_name=workspace_id,
                limit=top_k,
                scroll_filter=qdrant_filter,
                with_payload=True,
                with_vectors=True,
            )

            nodes: List[VectorNode] = []
            for record in records:
                node = self.point2node(record, workspace_id)
                nodes.append(node)

            return nodes

    # ==================== Insert Methods ====================

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Insert nodes into the workspace.

        Inserts one or more nodes into the workspace. If nodes don't have embeddings,
        they will be generated using the embedding_model. The workspace will be
        created automatically if it doesn't exist.

        Args:
            nodes: A single VectorNode or a list of VectorNode objects to insert.
                Nodes without vectors will have embeddings generated automatically.
            workspace_id: The ID of the workspace to insert nodes into.
            **kwargs: Additional keyword arguments passed to Qdrant's upsert method.

        Note:
            If a node with the same unique_id already exists, it will be updated
            (upsert behavior).
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        # Use parent's get_node_embeddings method
        nodes = self.get_node_embeddings(nodes)

        from qdrant_client.http.models import PointStruct

        points = [
            PointStruct(
                id=self._convert_id_to_uuid(node.unique_id),
                vector=node.vector,
                payload={
                    "workspace_id": workspace_id,
                    "content": node.content,
                    "metadata": node.metadata,
                    "original_id": node.unique_id,  # Store original ID in payload
                },
            )
            for node in nodes
        ]

        self._client.upsert(
            collection_name=workspace_id,
            points=points,
            **kwargs,
        )
        logger.info(f"insert points.size={len(points)} to workspace_id={workspace_id}")

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert using native Qdrant async client and async embedding.

        Inserts one or more nodes into the workspace asynchronously. If nodes don't
        have embeddings, they will be generated using async embedding_model. The workspace
        will be created automatically if it doesn't exist.

        Args:
            nodes: A single VectorNode or a list of VectorNode objects to insert.
                Nodes without vectors will have embeddings generated automatically.
            workspace_id: The ID of the workspace to insert nodes into.
            **kwargs: Additional keyword arguments passed to Qdrant's async upsert method.

        Note:
            If a node with the same unique_id already exists, it will be updated
            (upsert behavior).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        # Use parent's async_get_node_embeddings method
        nodes = await self.async_get_node_embeddings(nodes)

        from qdrant_client.http.models import PointStruct

        points = [
            PointStruct(
                id=self._convert_id_to_uuid(node.unique_id),
                vector=node.vector,
                payload={
                    "workspace_id": workspace_id,
                    "content": node.content,
                    "metadata": node.metadata,
                    "original_id": node.unique_id,  # Store original ID in payload
                },
            )
            for node in nodes
        ]

        await self._async_client.upsert(
            collection_name=workspace_id,
            points=points,
            **kwargs,
        )
        logger.info(f"async insert points.size={len(points)} to workspace_id={workspace_id}")

    # ==================== Delete Methods ====================

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Delete nodes from the workspace by their IDs.

        Args:
            node_ids: A single node ID or a list of node IDs to delete.
            workspace_id: The ID of the workspace containing the nodes to delete.
            **kwargs: Additional keyword arguments passed to Qdrant's delete method.

        Note:
            If the workspace doesn't exist, a warning is logged and the method returns
            without performing any operation.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        # Convert node IDs to UUIDs
        uuid_ids = [self._convert_id_to_uuid(node_id) for node_id in node_ids]

        from qdrant_client.http import models

        self._client.delete(
            collection_name=workspace_id,
            points_selector=models.PointIdsList(
                points=uuid_ids,
            ),
            **kwargs,
        )
        logger.info(f"delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete using native Qdrant async client.

        Args:
            node_ids: A single node ID or a list of node IDs to delete.
            workspace_id: The ID of the workspace containing the nodes to delete.
            **kwargs: Additional keyword arguments passed to Qdrant's async delete method.

        Note:
            If the workspace doesn't exist, a warning is logged and the method returns
            without performing any operation.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        # Convert node IDs to UUIDs
        uuid_ids = [self._convert_id_to_uuid(node_id) for node_id in node_ids]

        from qdrant_client.http import models

        await self._async_client.delete(
            collection_name=workspace_id,
            points_selector=models.PointIdsList(
                points=uuid_ids,
            ),
            **kwargs,
        )
        logger.info(f"async delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    # ==================== Close Methods ====================

    def close(self):
        """Close the Qdrant client.

        Closes the synchronous Qdrant client and releases any resources.
        Should be called when the vector store is no longer needed.
        """
        self._client.close()

    async def async_close(self):
        """Async close the Qdrant client.

        Closes the asynchronous Qdrant client and releases any resources.
        Should be called when the vector store is no longer needed in async contexts.
        """
        await self._async_client.close()
