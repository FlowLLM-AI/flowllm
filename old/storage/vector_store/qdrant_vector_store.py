import os
from typing import List, Iterable, Dict, Any, Optional

from loguru import logger
from pydantic import Field, PrivateAttr, model_validator
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range

from flowllm.context.service_context import C
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store.local_vector_store import LocalVectorStore


@C.register_vector_store("qdrant")
class QdrantVectorStore(LocalVectorStore):
    url: str | None = Field(default=None)
    host: str | None = Field(default_factory=lambda: os.getenv("FLOW_QDRANT_HOST", "localhost"))
    port: int | None = Field(default_factory=lambda: int(os.getenv("FLOW_QDRANT_PORT", "6333")))
    api_key: str | None = Field(default=None)
    distance: Distance = Field(default=Distance.COSINE)
    _client: QdrantClient = PrivateAttr()
    _async_client: AsyncQdrantClient = PrivateAttr()

    @model_validator(mode="after")
    def init_client(self):
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

        self._client = QdrantClient(**client_kwargs)
        self._async_client = AsyncQdrantClient(**client_kwargs)

        # Log connection info
        if self.url:
            logger.debug(f"Qdrant client initialized with url: {self.url}")
        else:
            logger.debug(f"Qdrant client initialized with host: {self.host}:{self.port}")
        return self

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a collection exists in Qdrant."""
        return self._client.collection_exists(collection_name=workspace_id)

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a collection from Qdrant."""
        return self._client.delete_collection(collection_name=workspace_id)

    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new collection in Qdrant."""
        return self._client.create_collection(
            collection_name=workspace_id,
            vectors_config=VectorParams(
                size=self.embedding_model.dimensions,
                distance=self.distance,
            ),
        )

    def iter_workspace_nodes(
        self, workspace_id: str, callback_fn=None, limit: int = 10000, **kwargs
    ) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace."""
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
                if callback_fn:
                    yield callback_fn(node)
                else:
                    yield node

            if next_offset is None:
                break
            offset = next_offset

    @staticmethod
    def point2node(point: models.Record, workspace_id: str) -> VectorNode:
        """Convert Qdrant point to VectorNode."""
        node = VectorNode(
            unique_id=str(point.id),
            workspace_id=workspace_id,
            content=point.payload.get("content", ""),
            metadata=point.payload.get("metadata", {}),
            vector=point.vector,
        )
        if hasattr(point, "score") and point.score is not None:
            node.metadata["score"] = point.score
        return node

    @staticmethod
    def _build_qdrant_filters(filter_dict: Optional[Dict[str, Any]] = None) -> Optional[Filter]:
        """Build Qdrant filter from filter_dict"""
        if not filter_dict:
            return None

        conditions = []
        for key, filter_value in filter_dict.items():
            # Handle nested keys by prefixing with metadata.
            qdrant_key = f"metadata.{key}" if not key.startswith("metadata.") else key

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

        return Filter(must=conditions)

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vectors in the workspace."""
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return []

        query_vector = self.embedding_model.get_embeddings(query)

        # Build filters from filter_dict
        qdrant_filter = self._build_qdrant_filters(filter_dict)

        results = self._client.search(
            collection_name=workspace_id,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
            with_vectors=True,
            **kwargs,
        )

        nodes: List[VectorNode] = []
        for scored_point in results:
            node = self.point2node(scored_point, workspace_id)
            node.metadata["score"] = scored_point.score
            nodes.append(node)

        return nodes

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Insert nodes into the workspace."""
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]
        now_embedded_nodes = self.embedding_model.get_node_embeddings(not_embedded_nodes)

        all_nodes = embedded_nodes + now_embedded_nodes

        points = [
            PointStruct(
                id=node.unique_id,
                vector=node.vector,
                payload={
                    "workspace_id": workspace_id,
                    "content": node.content,
                    "metadata": node.metadata,
                },
            )
            for node in all_nodes
        ]

        self._client.upsert(
            collection_name=workspace_id,
            points=points,
            **kwargs,
        )
        logger.info(f"insert points.size={len(points)} to workspace_id={workspace_id}")

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Delete nodes from the workspace by their IDs."""
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        self._client.delete(
            collection_name=workspace_id,
            points_selector=models.PointIdsList(
                points=node_ids,
            ),
            **kwargs,
        )
        logger.info(f"delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    # Async methods using native Qdrant async APIs
    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace using native Qdrant async client"""
        return await self._async_client.collection_exists(collection_name=workspace_id)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Async version of delete_workspace using native Qdrant async client"""
        return await self._async_client.delete_collection(collection_name=workspace_id)

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Async version of create_workspace using native Qdrant async client"""
        return await self._async_client.create_collection(
            collection_name=workspace_id,
            vectors_config=VectorParams(
                size=self.embedding_model.dimensions,
                distance=self.distance,
            ),
        )

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Async version of search using native Qdrant async client and async embedding"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return []

        # Use async embedding
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # Build filters from filter_dict
        qdrant_filter = self._build_qdrant_filters(filter_dict)

        results = await self._async_client.search(
            collection_name=workspace_id,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
            with_vectors=True,
            **kwargs,
        )

        nodes: List[VectorNode] = []
        for scored_point in results:
            node = self.point2node(scored_point, workspace_id)
            node.metadata["score"] = scored_point.score
            nodes.append(node)

        return nodes

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert using native Qdrant async client and async embedding"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]

        # Use async embedding
        now_embedded_nodes = await self.embedding_model.get_node_embeddings_async(not_embedded_nodes)

        all_nodes = embedded_nodes + now_embedded_nodes

        points = [
            PointStruct(
                id=node.unique_id,
                vector=node.vector,
                payload={
                    "workspace_id": workspace_id,
                    "content": node.content,
                    "metadata": node.metadata,
                },
            )
            for node in all_nodes
        ]

        await self._async_client.upsert(
            collection_name=workspace_id,
            points=points,
            **kwargs,
        )
        logger.info(f"async insert points.size={len(points)} to workspace_id={workspace_id}")

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete using native Qdrant async client"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        await self._async_client.delete(
            collection_name=workspace_id,
            points_selector=models.PointIdsList(
                points=node_ids,
            ),
            **kwargs,
        )
        logger.info(f"async delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    def close(self):
        """Close the Qdrant client."""
        self._client.close()

    async def async_close(self):
        """Async close the Qdrant client."""
        await self._async_client.close()


def main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "qdrant_rag_nodes_index"

    # Option 1: Use default localhost:6333
    qdrant = QdrantVectorStore(embedding_model=embedding_model, url="http://47.237.23.175:6333")

    # Option 2: Specify host and port
    # qdrant = QdrantVectorStore(embedding_model=embedding_model, host="localhost", port=6333)

    # Option 3: Use URL (e.g., for Qdrant Cloud)
    # qdrant = QdrantVectorStore(embedding_model=embedding_model, url="https://your-cluster.qdrant.io:6333", api_key="your-api-key")

    if qdrant.exist_workspace(workspace_id=workspace_id):
        qdrant.delete_workspace(workspace_id=workspace_id)
    qdrant.create_workspace(workspace_id=workspace_id)

    sample_nodes = [
        VectorNode(
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
            },
        ),
        VectorNode(
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
            },
        ),
    ]

    qdrant.insert(sample_nodes, workspace_id=workspace_id)

    logger.info("=" * 20 + " FILTER TEST " + "=" * 20)
    filter_dict = {"node_type": "n1"}
    results = qdrant.search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
    logger.info(f"Filtered results (node_type=n1): {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    logger.info("=" * 20 + " UNFILTERED TEST " + "=" * 20)
    results = qdrant.search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"Unfiltered results: {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    qdrant.dump_workspace(workspace_id=workspace_id)
    qdrant.delete_workspace(workspace_id=workspace_id)

    qdrant.close()


async def async_main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "async_qdrant_rag_nodes_index"

    # Use default localhost:6333
    qdrant = QdrantVectorStore(embedding_model=embedding_model, url="http://47.237.23.175:6333")

    # Clean up and create workspace
    if await qdrant.async_exist_workspace(workspace_id=workspace_id):
        await qdrant.async_delete_workspace(workspace_id=workspace_id)
    await qdrant.async_create_workspace(workspace_id=workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="async_qdrant_node1",
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            unique_id="async_qdrant_node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            unique_id="async_qdrant_node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
            },
        ),
        VectorNode(
            unique_id="async_qdrant_node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
            },
        ),
    ]

    # Test async insert
    await qdrant.async_insert(sample_nodes, workspace_id=workspace_id)

    logger.info("ASYNC TEST - " + "=" * 20)
    # Test async search with filter
    filter_dict = {"node_type": "n1"}
    results = await qdrant.async_search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async search without filter
    logger.info("ASYNC TEST WITHOUT FILTER - " + "=" * 20)
    results = await qdrant.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async update (delete + insert)
    node2_update = VectorNode(
        unique_id="async_qdrant_node2",
        workspace_id=workspace_id,
        content="AI is the future of humanity and technology.",
        metadata={
            "node_type": "n1",
            "updated": True,
        },
    )
    await qdrant.async_delete(node2_update.unique_id, workspace_id=workspace_id)
    await qdrant.async_insert(node2_update, workspace_id=workspace_id)

    logger.info("ASYNC Updated Result:")
    results = await qdrant.async_search("fish?", workspace_id=workspace_id, top_k=10)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Clean up
    await qdrant.async_dump_workspace(workspace_id=workspace_id)
    await qdrant.async_delete_workspace(workspace_id=workspace_id)

    await qdrant.async_close()


if __name__ == "__main__":
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    # import asyncio
    # asyncio.run(async_main())
