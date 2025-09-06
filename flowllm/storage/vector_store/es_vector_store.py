import asyncio
import os
from typing import List, Tuple, Iterable

from elasticsearch import Elasticsearch, AsyncElasticsearch
from elasticsearch.helpers import bulk, async_bulk
from loguru import logger
from pydantic import Field, PrivateAttr, model_validator

from flowllm.context.service_context import C
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store.local_vector_store import LocalVectorStore


@C.register_vector_store("elasticsearch")
class EsVectorStore(LocalVectorStore):
    hosts: str | List[str] = Field(default_factory=lambda: os.getenv("FLOW_ES_HOSTS", "http://localhost:9200"))
    basic_auth: str | Tuple[str, str] | None = Field(default=None)
    retrieve_filters: List[dict] = []
    _client: Elasticsearch = PrivateAttr()
    _async_client: AsyncElasticsearch = PrivateAttr()

    @model_validator(mode="after")
    def init_client(self):
        if isinstance(self.hosts, str):
            self.hosts = [self.hosts]
        self._client = Elasticsearch(hosts=self.hosts, basic_auth=self.basic_auth)
        self._async_client = AsyncElasticsearch(hosts=self.hosts, basic_auth=self.basic_auth)
        logger.info(f"Elasticsearch client initialized with hosts: {self.hosts}")
        return self

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        return self._client.indices.exists(index=workspace_id)

    def delete_workspace(self, workspace_id: str, **kwargs):
        return self._client.indices.delete(index=workspace_id, **kwargs)

    def create_workspace(self, workspace_id: str, **kwargs):
        body = {
            "mappings": {
                "properties": {
                    "workspace_id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "metadata": {"type": "object"},
                    "vector": {
                        "type": "dense_vector",
                        "dims": self.embedding_model.dimensions
                    }
                }
            }
        }
        return self._client.indices.create(index=workspace_id, body=body)

    def _iter_workspace_nodes(self, workspace_id: str, max_size: int = 10000, **kwargs) -> Iterable[VectorNode]:
        response = self._client.search(index=workspace_id, body={"query": {"match_all": {}}, "size": max_size})
        for doc in response['hits']['hits']:
            yield self.doc2node(doc, workspace_id)

    def refresh(self, workspace_id: str):
        self._client.indices.refresh(index=workspace_id)

    @staticmethod
    def doc2node(doc, workspace_id: str) -> VectorNode:
        node = VectorNode(**doc["_source"])
        node.workspace_id = workspace_id
        node.unique_id = doc["_id"]
        if "_score" in doc:
            node.metadata["score"] = doc["_score"] - 1
        return node

    def add_term_filter(self, key: str, value):
        if key:
            self.retrieve_filters.append({"term": {key: value}})
        return self

    def add_range_filter(self, key: str, gte=None, lte=None):
        if key:
            if gte is not None and lte is not None:
                self.retrieve_filters.append({"range": {key: {"gte": gte, "lte": lte}}})
            elif gte is not None:
                self.retrieve_filters.append({"range": {key: {"gte": gte}}})
            elif lte is not None:
                self.retrieve_filters.append({"range": {key: {"lte": lte}}})
        return self

    def clear_filter(self):
        self.retrieve_filters.clear()
        return self

    def search(self, query: str, workspace_id: str, top_k: int = 1, **kwargs) -> List[VectorNode]:
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return []

        query_vector = self.embedding_model.get_embeddings(query)
        body = {
            "query": {
                "script_score": {
                    "query": {"bool": {"must": self.retrieve_filters}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                        "params": {"query_vector": query_vector},
                    }
                }
            },
            "size": top_k
        }
        response = self._client.search(index=workspace_id, body=body, **kwargs)

        nodes: List[VectorNode] = []
        for doc in response['hits']['hits']:
            nodes.append(self.doc2node(doc, workspace_id))

        self.retrieve_filters.clear()
        return nodes

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, refresh: bool = True, **kwargs):
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
                    "vector": node.vector
                }
            } for node in embedded_nodes + now_embedded_nodes]
        status, error = bulk(self._client, docs, chunk_size=self.batch_size, **kwargs)
        logger.info(f"insert docs.size={len(docs)} status={status} error={error}")

        if refresh:
            self.refresh(workspace_id=workspace_id)

    def delete(self, node_ids: str | List[str], workspace_id: str, refresh: bool = True, **kwargs):
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        actions = [
            {
                "_op_type": "delete",
                "_index": workspace_id,
                "_id": node_id
            } for node_id in node_ids]
        status, error = bulk(self._client, actions, chunk_size=self.batch_size, **kwargs)
        logger.info(f"delete actions.size={len(actions)} status={status} error={error}")

        if refresh:
            self.refresh(workspace_id=workspace_id)

    # Async methods using native Elasticsearch async APIs
    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace using native ES async client"""
        return await self._async_client.indices.exists(index=workspace_id)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Async version of delete_workspace using native ES async client"""
        return await self._async_client.indices.delete(index=workspace_id, **kwargs)

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Async version of create_workspace using native ES async client"""
        body = {
            "mappings": {
                "properties": {
                    "workspace_id": {"type": "keyword"},
                    "content": {"type": "text"},
                    "metadata": {"type": "object"},
                    "vector": {
                        "type": "dense_vector",
                        "dims": self.embedding_model.dimensions
                    }
                }
            }
        }
        return await self._async_client.indices.create(index=workspace_id, body=body)

    async def async_refresh(self, workspace_id: str):
        """Async version of refresh using native ES async client"""
        await self._async_client.indices.refresh(index=workspace_id)

    async def async_search(self, query: str, workspace_id: str, top_k: int = 1, **kwargs) -> List[VectorNode]:
        """Async version of search using native ES async client and async embedding"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return []

        # Use async embedding
        query_vector = await self.embedding_model.get_embeddings_async(query)

        body = {
            "query": {
                "script_score": {
                    "query": {"bool": {"must": self.retrieve_filters}},
                    "script": {
                        "source": "cosineSimilarity(params.query_vector, 'vector') + 1.0",
                        "params": {"query_vector": query_vector},
                    }
                }
            },
            "size": top_k
        }
        response = await self._async_client.search(index=workspace_id, body=body, **kwargs)

        nodes: List[VectorNode] = []
        for doc in response['hits']['hits']:
            nodes.append(self.doc2node(doc, workspace_id))

        self.retrieve_filters.clear()
        return nodes

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, refresh: bool = True,
                           **kwargs):
        """Async version of insert using native ES async client and async embedding"""
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
                    "vector": node.vector
                }
            } for node in embedded_nodes + now_embedded_nodes]

        status, error = await async_bulk(self._async_client, docs, chunk_size=self.batch_size, **kwargs)
        logger.info(f"async insert docs.size={len(docs)} status={status} error={error}")

        if refresh:
            await self.async_refresh(workspace_id=workspace_id)

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, refresh: bool = True, **kwargs):
        """Async version of delete using native ES async client"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        actions = [
            {
                "_op_type": "delete",
                "_index": workspace_id,
                "_id": node_id
            } for node_id in node_ids]

        status, error = await async_bulk(self._async_client, actions, chunk_size=self.batch_size, **kwargs)
        logger.info(f"async delete actions.size={len(actions)} status={status} error={error}")

        if refresh:
            await self.async_refresh(workspace_id=workspace_id)

    def close(self):
        """Close the sync Elasticsearch client"""
        if hasattr(self, '_client'):
            self._client.close()

    async def aclose(self):
        """Close the async Elasticsearch client"""
        if hasattr(self, '_async_client'):
            await self._async_client.close()

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close the async client"""
        await self.aclose()

    def __del__(self):
        """Destructor to ensure clients are closed"""
        try:
            if hasattr(self, '_client'):
                self._client.close()
            # Note: Cannot close async client in __del__ as it requires await
            # Users should call aclose() explicitly or use async context manager
        except Exception:
            pass  # Ignore errors during cleanup


def main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "rag_nodes_index"
    hosts = "http://11.160.132.46:8200"
    es = EsVectorStore(hosts=hosts, embedding_model=embedding_model)
    if es.exist_workspace(workspace_id=workspace_id):
        es.delete_workspace(workspace_id=workspace_id)
    es.create_workspace(workspace_id=workspace_id)

    sample_nodes = [
        VectorNode(
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
            }
        ),
        VectorNode(
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
            }
        ),
        VectorNode(
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
            }
        ),
        VectorNode(
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
            }
        ),
    ]

    es.insert(sample_nodes, workspace_id=workspace_id, refresh=True)

    logger.info("=" * 20)
    results = es.add_term_filter(key="metadata.node_type", value="n1") \
        .search("What is AI?", top_k=5, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    logger.info("=" * 20)
    results = es.search("What is AI?", top_k=5, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)
    es.dump_workspace(workspace_id=workspace_id)
    es.delete_workspace(workspace_id=workspace_id)


async def async_main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "async_rag_nodes_index"
    hosts = "http://11.160.132.46:8200"

    # Use async context manager to ensure proper cleanup
    async with EsVectorStore(hosts=hosts, embedding_model=embedding_model) as es:
        # Clean up and create workspace
        if await es.async_exist_workspace(workspace_id=workspace_id):
            await es.async_delete_workspace(workspace_id=workspace_id)
        await es.async_create_workspace(workspace_id=workspace_id)

        sample_nodes = [
            VectorNode(
                unique_id="async_es_node1",
                workspace_id=workspace_id,
                content="Artificial intelligence is a technology that simulates human intelligence.",
                metadata={
                    "node_type": "n1",
                }
            ),
            VectorNode(
                unique_id="async_es_node2",
                workspace_id=workspace_id,
                content="AI is the future of mankind.",
                metadata={
                    "node_type": "n1",
                }
            ),
            VectorNode(
                unique_id="async_es_node3",
                workspace_id=workspace_id,
                content="I want to eat fish!",
                metadata={
                    "node_type": "n2",
                }
            ),
            VectorNode(
                unique_id="async_es_node4",
                workspace_id=workspace_id,
                content="The bigger the storm, the more expensive the fish.",
                metadata={
                    "node_type": "n1",
                }
            ),
        ]

        # Test async insert
        await es.async_insert(sample_nodes, workspace_id=workspace_id, refresh=True)

        logger.info("ASYNC TEST - " + "=" * 20)
        # Test async search with filter
        es.add_term_filter(key="metadata.node_type", value="n1")
        results = await es.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
        for r in results:
            logger.info(r.model_dump(exclude={"vector"}))
        logger.info("=" * 20)

        # Test async search without filter
        logger.info("ASYNC TEST WITHOUT FILTER - " + "=" * 20)
        results = await es.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
        for r in results:
            logger.info(r.model_dump(exclude={"vector"}))
        logger.info("=" * 20)

        # Test async update (delete + insert)
        node2_update = VectorNode(
            unique_id="async_es_node2",
            workspace_id=workspace_id,
            content="AI is the future of humanity and technology.",
            metadata={
                "node_type": "n1",
                "updated": True
            }
        )
        await es.async_delete(node2_update.unique_id, workspace_id=workspace_id, refresh=True)
        await es.async_insert(node2_update, workspace_id=workspace_id, refresh=True)

        logger.info("ASYNC Updated Result:")
        results = await es.async_search("fish?", workspace_id=workspace_id, top_k=10)
        for r in results:
            logger.info(r.model_dump(exclude={"vector"}))
        logger.info("=" * 20)

        # Clean up
        await es.async_dump_workspace(workspace_id=workspace_id)
        await es.async_delete_workspace(workspace_id=workspace_id)
    # Async client will be automatically closed when exiting the context manager


if __name__ == "__main__":
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    asyncio.run(async_main())
