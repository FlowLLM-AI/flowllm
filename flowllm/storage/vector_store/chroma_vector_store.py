import asyncio
import os
from functools import partial
from typing import List, Iterable, Dict, Any, Optional

import chromadb
from chromadb import Collection
from chromadb.config import Settings
from loguru import logger
from pydantic import Field, PrivateAttr, model_validator

# Disable ChromaDB telemetry to avoid PostHog warnings
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")

from flowllm.context.service_context import C
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store.local_vector_store import LocalVectorStore


@C.register_vector_store("chroma")
class ChromaVectorStore(LocalVectorStore):
    store_dir: str = Field(default="./chroma_vector_store")
    collections: dict = Field(default_factory=dict)
    _client: chromadb.ClientAPI = PrivateAttr()

    @model_validator(mode="after")
    def init_client(self):
        # Disable telemetry to avoid PostHog warnings
        settings = Settings(
            persist_directory=self.store_dir,
            anonymized_telemetry=False
        )
        self._client = chromadb.Client(settings)
        return self

    def _get_collection(self, workspace_id: str) -> Collection:
        if workspace_id not in self.collections:
            self.collections[workspace_id] = self._client.get_or_create_collection(workspace_id)
        return self.collections[workspace_id]

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        return workspace_id in [c.name for c in self._client.list_collections()]

    def delete_workspace(self, workspace_id: str, **kwargs):
        self._client.delete_collection(workspace_id)
        if workspace_id in self.collections:
            del self.collections[workspace_id]

    def create_workspace(self, workspace_id: str, **kwargs):
        self.collections[workspace_id] = self._client.get_or_create_collection(workspace_id)

    def iter_workspace_nodes(self, workspace_id: str, callback_fn=None, **kwargs) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace."""
        collection: Collection = self._get_collection(workspace_id)
        results = collection.get()
        for i in range(len(results["ids"])):
            node = VectorNode(workspace_id=workspace_id,
                              unique_id=results["ids"][i],
                              content=results["documents"][i],
                              metadata=results["metadatas"][i])
            if callback_fn:
                yield callback_fn(node)
            else:
                yield node

    @staticmethod
    def _build_chroma_filters(filter_dict: Optional[Dict[str, Any]] = None) -> Optional[Dict]:
        """Build ChromaDB where clause from filter_dict"""
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

    def search(self, query: str, workspace_id: str, top_k: int = 1, filter_dict: Optional[Dict[str, Any]] = None,
               **kwargs) -> List[VectorNode]:
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return []

        collection: Collection = self._get_collection(workspace_id)
        query_vector = self.embedding_model.get_embeddings(query)

        # Build where clause from filter_dict
        where_clause = self._build_chroma_filters(filter_dict)
        
        results = collection.query(
            query_embeddings=[query_vector], 
            n_results=top_k,
            where=where_clause
        )
        
        nodes = []
        for i in range(len(results["ids"][0])):
            node = VectorNode(workspace_id=workspace_id,
                              unique_id=results["ids"][0][i],
                              content=results["documents"][0][i],
                              metadata=results["metadatas"][0][i])
            # ChromaDB returns distances, convert to similarity score
            if results.get("distances") and len(results["distances"][0]) > i:
                distance = results["distances"][0][i]
                # Convert distance to similarity (assuming cosine distance)
                node.metadata["score"] = 1.0 - distance
            nodes.append(node)
        
        return nodes

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]
        now_embedded_nodes = self.embedding_model.get_node_embeddings(not_embedded_nodes)
        all_nodes = embedded_nodes + now_embedded_nodes

        collection: Collection = self._get_collection(workspace_id)
        collection.add(ids=[n.unique_id for n in all_nodes],
                       embeddings=[n.vector for n in all_nodes],
                       documents=[n.content for n in all_nodes],
                       metadatas=[n.metadata for n in all_nodes])

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        collection: Collection = self._get_collection(workspace_id)
        collection.delete(ids=node_ids)


    async def async_search(self, query: str, workspace_id: str, top_k: int = 1,
                           filter_dict: Optional[Dict[str, Any]] = None, **kwargs) -> List[VectorNode]:
        """Async version of search using async embedding and run_in_executor for ChromaDB operations"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
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
            partial(collection.query, query_embeddings=[query_vector], n_results=top_k, where=where_clause)
        )

        nodes = []
        for i in range(len(results["ids"][0])):
            node = VectorNode(workspace_id=workspace_id,
                              unique_id=results["ids"][0][i],
                              content=results["documents"][0][i],
                              metadata=results["metadatas"][0][i])
            # ChromaDB returns distances, convert to similarity score
            if results.get("distances") and len(results["distances"][0]) > i:
                distance = results["distances"][0][i]
                # Convert distance to similarity (assuming cosine distance)
                node.metadata["score"] = 1.0 - distance
            nodes.append(node)
        
        return nodes

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert using async embedding and run_in_executor for ChromaDB operations"""
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
            partial(collection.add,
                    ids=[n.unique_id for n in all_nodes],
                    embeddings=[n.vector for n in all_nodes],
                    documents=[n.content for n in all_nodes],
                    metadatas=[n.metadata for n in all_nodes])
        )

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete using run_in_executor for ChromaDB operations"""
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        # Execute ChromaDB operations in thread pool
        loop = asyncio.get_event_loop()
        collection = await loop.run_in_executor(C.thread_pool, self._get_collection, workspace_id)
        await loop.run_in_executor(C.thread_pool, partial(collection.delete, ids=node_ids))


def main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "chroma_test_index"

    chroma_store = ChromaVectorStore(
        embedding_model=embedding_model,
        store_dir="./chroma_test_db"
    )

    if chroma_store.exist_workspace(workspace_id):
        chroma_store.delete_workspace(workspace_id)
    chroma_store.create_workspace(workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="node1",
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
                "category": "tech"
            }
        ),
        VectorNode(
            unique_id="node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
                "category": "tech"
            }
        ),
        VectorNode(
            unique_id="node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
                "category": "food"
            }
        ),
        VectorNode(
            unique_id="node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
                "category": "food"
            }
        ),
    ]

    chroma_store.insert(sample_nodes, workspace_id=workspace_id)

    logger.info("=" * 20)
    results = chroma_store.search("What is AI?", top_k=5, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test filter_dict
    logger.info("=" * 20 + " FILTER TEST " + "=" * 20)
    filter_dict = {"node_type": "n1"}
    results = chroma_store.search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
    logger.info(f"Filtered results (node_type=n1): {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    node2_update = VectorNode(
        unique_id="node2",
        workspace_id=workspace_id,
        content="AI is the future of humanity and technology.",
        metadata={
            "node_type": "n1",
            "category": "tech",
            "updated": True
        }
    )
    chroma_store.delete(node2_update.unique_id, workspace_id=workspace_id)
    chroma_store.insert(node2_update, workspace_id=workspace_id)

    logger.info("Updated Result:")
    results = chroma_store.search("fish?", top_k=10, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    chroma_store.dump_workspace(workspace_id=workspace_id)

    chroma_store.delete_workspace(workspace_id=workspace_id)


async def async_main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "chroma_async_test_index"

    chroma_store = ChromaVectorStore(
        embedding_model=embedding_model,
        store_dir="./async_chroma_async_test_db"
    )

    # Clean up and create workspace
    if await chroma_store.async_exist_workspace(workspace_id):
        await chroma_store.async_delete_workspace(workspace_id)
    await chroma_store.async_create_workspace(workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="async_node1",
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
                "category": "tech"
            }
        ),
        VectorNode(
            unique_id="async_node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
                "category": "tech"
            }
        ),
        VectorNode(
            unique_id="async_node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
                "category": "food"
            }
        ),
        VectorNode(
            unique_id="async_node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
                "category": "food"
            }
        ),
    ]

    # Test async insert
    await chroma_store.async_insert(sample_nodes, workspace_id=workspace_id)

    logger.info("ASYNC TEST - " + "=" * 20)
    # Test async search
    results = await chroma_store.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async update (delete + insert)
    node2_update = VectorNode(
        unique_id="async_node2",
        workspace_id=workspace_id,
        content="AI is the future of humanity and technology.",
        metadata={
            "node_type": "n1",
            "category": "tech",
            "updated": True
        }
    )
    await chroma_store.async_delete(node2_update.unique_id, workspace_id=workspace_id)
    await chroma_store.async_insert(node2_update, workspace_id=workspace_id)

    logger.info("ASYNC Updated Result:")
    results = await chroma_store.async_search("fish?", top_k=10, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Clean up
    await chroma_store.async_dump_workspace(workspace_id=workspace_id)
    await chroma_store.async_delete_workspace(workspace_id=workspace_id)


if __name__ == "__main__":
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    # asyncio.run(async_main())
