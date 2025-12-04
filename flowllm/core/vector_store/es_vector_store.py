"""Elasticsearch vector store implementation.

This module provides an Elasticsearch-based vector store that stores vector nodes
in Elasticsearch indices. It supports workspace management, vector similarity search,
metadata filtering using Elasticsearch query DSL, and provides both synchronous and
asynchronous operations using native Elasticsearch clients.
"""

import os
from typing import List, Tuple, Iterable, Dict, Any, Optional

from loguru import logger

from .local_vector_store import LocalVectorStore
from ..context import C
from ..schema import VectorNode


@C.register_vector_store("elasticsearch")
class EsVectorStore(LocalVectorStore):
    """Elasticsearch vector store implementation.

    This class provides a vector store backend using Elasticsearch for storing and
    searching vector embeddings. It supports both synchronous and asynchronous operations
    using native Elasticsearch clients, and includes metadata filtering capabilities
    using Elasticsearch query DSL.

    Attributes:
        hosts: Elasticsearch host(s) as a string or list of strings. Defaults to
            the FLOW_ES_HOSTS environment variable or "http://localhost:9200".
        basic_auth: Optional basic authentication credentials as a string or
            tuple of (username, password).
        batch_size: Batch size for bulk operations. Defaults to 100.
    """

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
            **kwargs: Additional keyword arguments passed to LocalVectorStore.
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

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if an Elasticsearch index (workspace) exists.

        Args:
            workspace_id: The identifier of the workspace/index to check.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        return self._client.indices.exists(index=workspace_id)

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete an Elasticsearch index (workspace).

        Args:
            workspace_id: The identifier of the workspace/index to delete.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.
        """
        return self._client.indices.delete(index=workspace_id, **kwargs)

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

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces (indices) in Elasticsearch.

        Returns:
            List[str]: Workspace identifiers (index names).
        """
        return list(self._client.indices.get(index="*").keys())

    def iter_workspace_nodes(
        self,
        workspace_id: str,
        max_size: int = 10000,
        **kwargs,
    ) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace.

        Args:
            workspace_id: The identifier of the workspace to iterate over.
            max_size: Maximum number of nodes to retrieve (default: 10000).
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Yields:
            VectorNode: Vector nodes from the workspace.
        """
        response = self._client.search(index=workspace_id, body={"query": {"match_all": {}}, "size": max_size})
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id)
            yield node

    def refresh(self, workspace_id: str):
        """Refresh an Elasticsearch index to make recent changes visible for search.

        Args:
            workspace_id: The identifier of the workspace/index to refresh.
        """
        self._client.indices.refresh(index=workspace_id)

    @staticmethod
    def doc2node(doc, workspace_id: str) -> VectorNode:
        """Convert an Elasticsearch document to a VectorNode.

        Args:
            doc: The Elasticsearch document hit from a search response.
            workspace_id: The workspace identifier to assign to the node.

        Returns:
            VectorNode: A VectorNode instance created from the document data.
        """
        node = VectorNode(**doc["_source"])
        node.workspace_id = workspace_id
        node.unique_id = doc["_id"]
        if "_score" in doc:
            node.metadata["score"] = doc["_score"] - 1
        return node

    @staticmethod
    def _build_es_filters(filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Build Elasticsearch filter clauses from filter_dict.

        Converts a filter dictionary into Elasticsearch query filter clauses.
        Supports both term filters (exact match) and range filters (gte, lte, gt, lt).

        Args:
            filter_dict: Dictionary of filter conditions. Keys are metadata field names,
                values can be exact match values or range dictionaries like
                {"gte": 1, "lte": 10}.

        Returns:
            List[Dict]: List of Elasticsearch filter clauses.
        """
        if not filter_dict:
            return []

        filters = []
        for key, filter_value in filter_dict.items():
            # Handle nested keys by prefixing with metadata.
            es_key = f"metadata.{key}" if not key.startswith("metadata.") else key

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
            else:
                # Term filter: direct value comparison
                filters.append({"term": {es_key: filter_value}})

        return filters

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity.

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model.
            workspace_id: The identifier of the workspace to search in.
            top_k: Maximum number of results to return (default: 1).
            filter_dict: Optional dictionary of metadata filters to apply.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            List[VectorNode]: List of matching vector nodes sorted by similarity score.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        query_vector = self.embedding_model.get_embeddings(query)

        # Build filters from filter_dict
        es_filters = self._build_es_filters(filter_dict)

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
        response = self._client.search(index=workspace_id, body=body, **kwargs)

        nodes: List[VectorNode] = []
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id)
            node.metadata["score"] = doc["_score"] - 1  # Adjust score since we added 1.0
            nodes.append(node)

        return nodes

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
        now_embedded_nodes = self.embedding_model.get_node_embeddings(not_embedded_nodes)

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

    # Async methods using native Elasticsearch async APIs
    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if an Elasticsearch index (workspace) exists (async).

        Args:
            workspace_id: The identifier of the workspace/index to check.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        return await self._async_client.indices.exists(index=workspace_id)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Delete an Elasticsearch index (workspace) (async).

        Args:
            workspace_id: The identifier of the workspace/index to delete.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.
        """
        return await self._async_client.indices.delete(index=workspace_id, **kwargs)

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

    async def async_refresh(self, workspace_id: str):
        """Refresh an Elasticsearch index to make recent changes visible for search (async).

        Args:
            workspace_id: The identifier of the workspace/index to refresh.
        """
        await self._async_client.indices.refresh(index=workspace_id)

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity (async).

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model's async method.
            workspace_id: The identifier of the workspace to search in.
            top_k: Maximum number of results to return (default: 1).
            filter_dict: Optional dictionary of metadata filters to apply.
            **kwargs: Additional keyword arguments passed to Elasticsearch API.

        Returns:
            List[VectorNode]: List of matching vector nodes sorted by similarity score.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Use async embedding
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # Build filters from filter_dict
        es_filters = self._build_es_filters(filter_dict)

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
        response = await self._async_client.search(index=workspace_id, body=body, **kwargs)

        nodes: List[VectorNode] = []
        for doc in response["hits"]["hits"]:
            node = self.doc2node(doc, workspace_id)
            node.metadata["score"] = doc["_score"] - 1  # Adjust score since we added 1.0
            nodes.append(node)

        return nodes

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
        now_embedded_nodes = await self.embedding_model.get_node_embeddings_async(not_embedded_nodes)

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

    def close(self):
        """Close the synchronous Elasticsearch client connection."""
        self._client.close()

    async def async_close(self):
        """Close the asynchronous Elasticsearch client connection."""
        await self._async_client.close()
