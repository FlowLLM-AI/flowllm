"""Elasticsearch vector store implementation.

This module provides an Elasticsearch-based vector store that stores vector nodes
in Elasticsearch indices. It supports workspace management, vector similarity search,
metadata filtering using Elasticsearch query DSL, and provides both synchronous and
asynchronous operations using native Elasticsearch clients.
"""

import os
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from loguru import logger

from .memory_vector_store import MemoryVectorStore
from ..context import C
from ..schema import VectorNode


@C.register_vector_store("elasticsearch")
class EsVectorStore(MemoryVectorStore):
    """Elasticsearch vector store implementation.

    This class provides a vector store backend using Elasticsearch for storing and
    searching vector embeddings. It supports both synchronous and asynchronous operations
    using native Elasticsearch clients, and includes metadata filtering capabilities
    using Elasticsearch query DSL.

    Inherits from MemoryVectorStore for utility methods like _load_from_path,
    _dump_to_path, and _matches_filters.

    Attributes:
        hosts: Elasticsearch host(s) as a string or list of strings. Defaults to
            the FLOW_ES_HOSTS environment variable or "http://localhost:9200".
        basic_auth: Optional basic authentication credentials as a string or
            tuple of (username, password).
        batch_size: Batch size for bulk operations. Defaults to 1024.
    """

    # ==================== Initialization ====================

    def __init__(
        self,
        hosts: str | List[str] = "http://localhost:9200",
        basic_auth: str | Tuple[str, str] | None = None,
        batch_size: int = 1024,
        **kwargs,
    ):
        """Initialize Elasticsearch clients.

        Args:
            hosts: Elasticsearch host(s) as a string or list of strings.
            basic_auth: Optional basic authentication credentials.
            batch_size: Batch size for bulk operations.
            **kwargs: Additional keyword arguments passed to MemoryVectorStore.
        """
        super().__init__(**kwargs)
        self.hosts = hosts or os.getenv("FLOW_ES_HOSTS", "http://localhost:9200")
        self.basic_auth = basic_auth
        self.batch_size = batch_size

        if isinstance(self.hosts, str):
            self.hosts = [self.hosts]

        from elasticsearch import Elasticsearch, AsyncElasticsearch

        self._client = Elasticsearch(hosts=self.hosts, basic_auth=self.basic_auth)
        self._async_client = AsyncElasticsearch(hosts=self.hosts, basic_auth=self.basic_auth)
        logger.info(f"Elasticsearch client initialized with hosts={self.hosts} basic_auth={self.basic_auth}")

    # ==================== Static Helper Methods ====================

    @staticmethod
    def doc2node(doc, workspace_id: str, is_vector_search: bool = False) -> VectorNode:
        """Convert an Elasticsearch document to a VectorNode.

        Args:
            doc: The Elasticsearch document hit from a search response.
            workspace_id: The workspace identifier to assign to the node.
            is_vector_search: Whether this is a vector similarity search result.
                If True, the score is adjusted by subtracting 1.0 (since we add 1.0
                in script_score to avoid negative scores).

        Returns:
            VectorNode: A VectorNode instance created from the document data.
        """
        node = VectorNode(**doc["_source"])
        node.workspace_id = workspace_id
        node.unique_id = doc["_id"]
        # Only adjust score for vector search (where we added 1.0 in script_score)
        if is_vector_search and "_score" in doc:
            node.metadata["score"] = doc["_score"] - 1
        return node

    # Top-level VectorNode fields that are stored directly in Elasticsearch
    # (not nested under metadata)
    _TOP_LEVEL_FIELDS = {"unique_id", "workspace_id", "content"}

    @staticmethod
    def _build_es_filters(filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Build Elasticsearch filter clauses from filter_dict.

        Converts a filter dictionary into Elasticsearch query filter clauses.
        Supports both term filters (exact match) and range filters (gte, lte, gt, lt).

        Handles top-level VectorNode fields (unique_id, workspace_id, content)
        separately from metadata fields. The unique_id field is stored as Elasticsearch's
        _id, so it uses the ids query. Other top-level fields are stored directly in
        _source without the metadata prefix.

        Args:
            filter_dict: Dictionary of filter conditions. Keys can be:
                - Top-level VectorNode fields: unique_id, workspace_id, content
                - Metadata fields: node_type, category, etc. (auto-prefixed with "metadata.")
                - Already-prefixed metadata fields: metadata.node_type, etc.
                Values can be exact match values or range dictionaries like
                {"gte": 1, "lte": 10}.

        Returns:
            List[Dict]: List of Elasticsearch filter clauses.
        """
        if not filter_dict:
            return []

        filters = []
        for key, filter_value in filter_dict.items():
            # Handle unique_id specially - it's stored as Elasticsearch's _id
            if key == "unique_id":
                # Use ids query to filter by document ID
                # Support both single value and list of values
                if isinstance(filter_value, list):
                    filters.append({"ids": {"values": filter_value}})
                else:
                    filters.append({"ids": {"values": [filter_value]}})
                continue

            # Determine the Elasticsearch field key
            if key in EsVectorStore._TOP_LEVEL_FIELDS:
                # Top-level fields (workspace_id, content) are stored directly in _source
                es_key = key
            elif key.startswith("metadata."):
                # Already prefixed with metadata.
                es_key = key
            else:
                # Assume it's a metadata field and prefix it
                es_key = f"metadata.{key}"

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
                    filters.append({"range": {es_key: range_conditions}})
            elif isinstance(filter_value, list):
                # List filter: use terms query for OR logic
                filters.append({"terms": {es_key: filter_value}})
            else:
                # Term filter: direct value comparison
                filters.append({"term": {es_key: filter_value}})

        return filters

    # ==================== ES-specific Helper Methods ====================

    def refresh(self, workspace_id: str):
        """Refresh an Elasticsearch index to make recent changes visible for search.

        Args:
            workspace_id: The identifier of the workspace/index to refresh.
        """
        self._client.indices.refresh(index=workspace_id)

    async def async_refresh(self, workspace_id: str):
        """Refresh an Elasticsearch index to make recent changes visible for search (async).

        Args:
            workspace_id: The identifier of the workspace/index to refresh.
        """
        await self._async_client.indices.refresh(index=workspace_id)

    # ==================== Workspace Management Methods ====================

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if an Elasticsearch index (workspace) exists.

        Args:
            workspace_id: The identifier of the workspace/index to check.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        return self._client.indices.exists(index=workspace_id)

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if an Elasticsearch index (workspace) exists (async).

        Args:
            workspace_id: The identifier of the workspace/index to check.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        return await self._async_client.indices.exists(index=workspace_id)

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete an Elasticsearch index (workspace).

        Args:
            workspace_id: The identifier of the workspace/index to delete.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.
        """
        return self._client.indices.delete(index=workspace_id, **kwargs)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Delete an Elasticsearch index (workspace) (async).

        Args:
            workspace_id: The identifier of the workspace/index to delete.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.
        """
        return await self._async_client.indices.delete(index=workspace_id, **kwargs)

    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new Elasticsearch index (workspace) with vector field mappings.

        Args:
            workspace_id: The identifier of the workspace/index to create.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            The response from Elasticsearch create index API.
        """
        body = {
            "mappings": {
                "properties": {
                    "workspace_id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "metadata": {"type": "object"},
                    "vector": {
                        "type": "dense_vector",
                        "dims": self.embedding_model.dimensions,
                    },
                },
            },
        }
        return self._client.indices.create(index=workspace_id, body=body)

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Create a new Elasticsearch index (workspace) with vector field mappings (async).

        Args:
            workspace_id: The identifier of the workspace/index to create.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            The response from Elasticsearch create index API.
        """
        body = {
            "mappings": {
                "properties": {
                    "workspace_id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "metadata": {"type": "object"},
                    "vector": {
                        "type": "dense_vector",
                        "dims": self.embedding_model.dimensions,
                    },
                },
            },
        }
        return await self._async_client.indices.create(index=workspace_id, body=body)

    def list_workspace_nodes(
        self,
        workspace_id: str,
        max_size: int = 10000,
        **kwargs,
    ) -> List[VectorNode]:
        """List all nodes in a workspace.

        Args:
            workspace_id: The identifier of the workspace to list.
            max_size: Maximum number of nodes to retrieve (default: 10000).
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            List[VectorNode]: Vector nodes from the workspace.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        response = self._client.search(index=workspace_id, body={"query": {"match_all": {}}, "size": max_size})
        nodes = []
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id, is_vector_search=False)
            nodes.append(node)
        return nodes

    async def async_list_workspace_nodes(
        self,
        workspace_id: str,
        max_size: int = 10000,
        **kwargs,
    ) -> List[VectorNode]:
        """List all nodes in a workspace (async).

        Args:
            workspace_id: The identifier of the workspace to list.
            max_size: Maximum number of nodes to retrieve (default: 10000).
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            List[VectorNode]: Vector nodes from the workspace.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        response = await self._async_client.search(
            index=workspace_id,
            body={"query": {"match_all": {}}, "size": max_size},
        )
        nodes = []
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id, is_vector_search=False)
            nodes.append(node)
        return nodes

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

        nodes = []
        node_size = 0
        for node in self.list_workspace_nodes(workspace_id=src_workspace_id, **kwargs):
            nodes.append(node)
            node_size += 1
            if len(nodes) >= self.batch_size:
                self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
                nodes.clear()

        if nodes:
            self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
        return {"size": node_size}

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
        nodes = []
        node_size = 0
        for node in src_nodes:
            nodes.append(node)
            node_size += 1
            if len(nodes) >= self.batch_size:
                await self.async_insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
                nodes.clear()

        if nodes:
            await self.async_insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
        return {"size": node_size}

    def list_workspace(self, **kwargs) -> List[str]:
        """List all existing workspaces (indices) in Elasticsearch.

        Returns:
            List[str]: Workspace identifiers (index names).
        """
        return list(self._client.indices.get(index="*").keys())

    async def async_list_workspace(self, **kwargs) -> List[str]:
        """List all existing workspaces (indices) in Elasticsearch (async).

        Returns:
            List[str]: Workspace identifiers (index names).
        """
        result = await self._async_client.indices.get(index="*")
        return list(result.keys())

    # ==================== Search Methods ====================

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity.

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model. If empty/None, performs filter-only search.
            workspace_id: The identifier of the workspace to search in.
            top_k: Maximum number of results to return (default: 1).
            filter_dict: Optional dictionary of metadata filters to apply.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            List[VectorNode]: List of matching vector nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a "score"
                key in metadata. When query is empty, nodes are returned based on
                filter criteria without scores.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Build filters from filter_dict
        es_filters = self._build_es_filters(filter_dict)

        # When query is empty, degrade to filter-only search
        use_vector_search = bool(query)

        if use_vector_search:
            query_vector = self.get_embeddings(query)
            body = {
                "query": {
                    "script_score": {
                        "query": {"bool": {"must": es_filters}} if es_filters else {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                            "params": {"query_vector": query_vector},
                        },
                    },
                },
                "size": top_k,
            }
        else:
            # Filter-only search without vector similarity
            body = {
                "query": {"bool": {"must": es_filters}} if es_filters else {"match_all": {}},
                "size": top_k,
            }

        response = self._client.search(index=workspace_id, body=body, **kwargs)

        nodes: List[VectorNode] = []
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id, is_vector_search=use_vector_search)
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
        """Search for similar vector nodes using cosine similarity (async).

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model's async method. If empty/None, performs filter-only search.
            workspace_id: The identifier of the workspace to search in.
            top_k: Maximum number of results to return (default: 1).
            filter_dict: Optional dictionary of metadata filters to apply.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            List[VectorNode]: List of matching vector nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a "score"
                key in metadata. When query is empty, nodes are returned based on
                filter criteria without scores.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Build filters from filter_dict
        es_filters = self._build_es_filters(filter_dict)

        # When query is empty, degrade to filter-only search
        use_vector_search = bool(query)

        if use_vector_search:
            # Use async embedding
            query_vector = await self.async_get_embeddings(query)
            body = {
                "query": {
                    "script_score": {
                        "query": {"bool": {"must": es_filters}} if es_filters else {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                            "params": {"query_vector": query_vector},
                        },
                    },
                },
                "size": top_k,
            }
        else:
            # Filter-only search without vector similarity
            body = {
                "query": {"bool": {"must": es_filters}} if es_filters else {"match_all": {}},
                "size": top_k,
            }

        response = await self._async_client.search(index=workspace_id, body=body, **kwargs)

        nodes: List[VectorNode] = []
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id, is_vector_search=use_vector_search)
            nodes.append(node)

        return nodes

    # ==================== Insert Methods ====================

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, refresh: bool = True, **kwargs):
        """Insert vector nodes into the Elasticsearch index.

        Args:
            nodes: A single VectorNode or list of VectorNodes to insert.
            workspace_id: The identifier of the workspace to insert into.
            refresh: Whether to refresh the index after insertion (default: True).
            **kwargs: Additional keyword arguments passed to Elasticsearch bulk API.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]
        now_embedded_nodes = self.get_node_embeddings(not_embedded_nodes) if not_embedded_nodes else []

        docs = [
            {
                "_op_type": "index",
                "_index": workspace_id,
                "_id": node.unique_id,
                "_source": {
                    "workspace_id": workspace_id,
                    "content": node.content,
                    "metadata": node.metadata,
                    "vector": node.vector,
                },
            }
            for node in embedded_nodes + now_embedded_nodes
        ]
        from elasticsearch.helpers import bulk

        status, error = bulk(self._client, docs, chunk_size=self.batch_size, **kwargs)
        logger.info(f"insert docs.size={len(docs)} status={status} error={error}")

        if refresh:
            self.refresh(workspace_id=workspace_id)

    async def async_insert(
        self,
        nodes: VectorNode | List[VectorNode],
        workspace_id: str,
        refresh: bool = True,
        **kwargs,
    ):
        """Insert vector nodes into the Elasticsearch index (async).

        Args:
            nodes: A single VectorNode or list of VectorNodes to insert.
            workspace_id: The identifier of the workspace to insert into.
            refresh: Whether to refresh the index after insertion (default: True).
            **kwargs: Additional keyword arguments passed to Elasticsearch bulk API.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]

        # Use async embedding
        now_embedded_nodes = await self.async_get_node_embeddings(not_embedded_nodes) if not_embedded_nodes else []

        docs = [
            {
                "_op_type": "index",
                "_index": workspace_id,
                "_id": node.unique_id,
                "_source": {
                    "workspace_id": workspace_id,
                    "content": node.content,
                    "metadata": node.metadata,
                    "vector": node.vector,
                },
            }
            for node in embedded_nodes + now_embedded_nodes
        ]

        from elasticsearch.helpers import async_bulk

        status, error = await async_bulk(self._async_client, docs, chunk_size=self.batch_size, **kwargs)
        logger.info(f"async insert docs.size={len(docs)} status={status} error={error}")

        if refresh:
            await self.async_refresh(workspace_id=workspace_id)

    # ==================== Delete Methods ====================

    def delete(self, node_ids: str | List[str], workspace_id: str, refresh: bool = True, **kwargs):
        """Delete vector nodes from the Elasticsearch index.

        Args:
            node_ids: A single node ID or list of node IDs to delete.
            workspace_id: The identifier of the workspace to delete from.
            refresh: Whether to refresh the index after deletion (default: True).
            **kwargs: Additional keyword arguments passed to Elasticsearch bulk API.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        actions = [
            {
                "_op_type": "delete",
                "_index": workspace_id,
                "_id": node_id,
            }
            for node_id in node_ids
        ]
        from elasticsearch.helpers import bulk

        status, error = bulk(self._client, actions, chunk_size=self.batch_size, **kwargs)
        logger.info(f"delete actions.size={len(actions)} status={status} error={error}")

        if refresh:
            self.refresh(workspace_id=workspace_id)

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, refresh: bool = True, **kwargs):
        """Delete vector nodes from the Elasticsearch index (async).

        Args:
            node_ids: A single node ID or list of node IDs to delete.
            workspace_id: The identifier of the workspace to delete from.
            refresh: Whether to refresh the index after deletion (default: True).
            **kwargs: Additional keyword arguments passed to Elasticsearch bulk API.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        actions = [
            {
                "_op_type": "delete",
                "_index": workspace_id,
                "_id": node_id,
            }
            for node_id in node_ids
        ]

        from elasticsearch.helpers import async_bulk

        status, error = await async_bulk(self._async_client, actions, chunk_size=self.batch_size, **kwargs)
        logger.info(f"async delete actions.size={len(actions)} status={status} error={error}")

        if refresh:
            await self.async_refresh(workspace_id=workspace_id)

    # ==================== Close Methods ====================

    def close(self):
        """Close the synchronous Elasticsearch client connection."""
        self._client.close()

    async def async_close(self):
        """Close the asynchronous Elasticsearch client connection."""
        await self._async_client.close()
