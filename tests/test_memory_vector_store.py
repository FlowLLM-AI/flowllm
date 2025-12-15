"""Test script for all VectorStore implementations.

This script provides test classes for both synchronous and asynchronous
vector store operations. It supports testing all VectorStore implementations
through a configurable factory pattern.

Supported vector stores:
- memory: MemoryVectorStore (in-memory storage)
- local: LocalVectorStore (local file-based storage)
- chroma: ChromaVectorStore (ChromaDB backend)
- elasticsearch: EsVectorStore (Elasticsearch backend)
- qdrant: QdrantVectorStore (Qdrant backend)
- pgvector: PgVectorStore (PostgreSQL pgvector backend)

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint

For specific backends:
- Elasticsearch: FLOW_ES_HOSTS (default: http://localhost:9200)
- Qdrant: FLOW_QDRANT_HOST, FLOW_QDRANT_PORT (default: localhost:6333)
- PgVector: FLOW_PGVECTOR_CONNECTION_STRING (default: postgresql://localhost/postgres)

Usage:
    python test_memory_vector_store.py <store_type>  # Test specific store (sync + async)
    python test_memory_vector_store.py --all         # Test all vector stores
    python test_memory_vector_store.py delete        # Delete all test-generated files

Examples:
    python test_memory_vector_store.py memory        # Test MemoryVectorStore
    python test_memory_vector_store.py local         # Test LocalVectorStore
    python test_memory_vector_store.py chroma        # Test ChromaVectorStore
    python test_memory_vector_store.py elasticsearch # Test EsVectorStore
    python test_memory_vector_store.py qdrant        # Test QdrantVectorStore
    python test_memory_vector_store.py pgvector      # Test PgVectorStore
    python test_memory_vector_store.py --all         # Test all vector stores
    python test_memory_vector_store.py delete        # Delete all test files/directories
"""

import asyncio
import shutil
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Literal, get_args

from loguru import logger

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.schema.vector_node import VectorNode
from flowllm.core.utils import load_env
from flowllm.core.vector_store.base_vector_store import BaseVectorStore
from flowllm.core.vector_store.chroma_vector_store import ChromaVectorStore
from flowllm.core.vector_store.es_vector_store import EsVectorStore
from flowllm.core.vector_store.local_vector_store import LocalVectorStore
from flowllm.core.vector_store.memory_vector_store import MemoryVectorStore
from flowllm.core.vector_store.pgvector_vector_store import PgVectorStore
from flowllm.core.vector_store.qdrant_vector_store import QdrantVectorStore

load_env()

# ==================== Vector Store Factory ====================


# All supported store types
STORE_TYPES = Literal["memory", "local", "chroma", "elasticsearch", "qdrant", "pgvector"]


class VectorStoreFactory:
    """Factory class for creating vector store instances."""

    @staticmethod
    def get_all_store_types() -> List[str]:
        """Get all supported store types.

        Returns:
            List[str]: All supported store type names.
        """
        return list(get_args(STORE_TYPES))

    @staticmethod
    def create(
        store_type: STORE_TYPES,
        embedding_model: OpenAICompatibleEmbeddingModel,
        store_dir: str = "./test_vector_store",
        es_hosts: str = "http://11.160.132.46:8200",
        qdrant_url: str = "http://11.160.132.46:6333",
        pg_connection_string: str = "postgresql://localhost/postgres",
        pg_async_connection_string: str = "postgresql://localhost/postgres",
    ) -> BaseVectorStore:
        """Create a vector store instance based on the specified type.

        Args:
            store_type: Type of vector store to create
            embedding_model: Embedding model instance to use
            store_dir: Directory for file-based storage (LocalVectorStore, ChromaVectorStore)
            es_hosts: Elasticsearch host URL (for EsVectorStore)
            qdrant_url: Qdrant server URL (for QdrantVectorStore)
            pg_connection_string: PostgreSQL connection string (for PgVectorStore)
            pg_async_connection_string: Async PostgreSQL connection string (for PgVectorStore)

        Returns:
            BaseVectorStore: The created vector store instance

        Raises:
            ValueError: If the store type is unknown
        """
        if store_type == "memory":
            return MemoryVectorStore(embedding_model=embedding_model)
        elif store_type == "local":
            return LocalVectorStore(embedding_model=embedding_model, store_dir=store_dir)
        elif store_type == "chroma":
            return ChromaVectorStore(embedding_model=embedding_model, store_dir=store_dir)
        elif store_type == "elasticsearch":
            return EsVectorStore(hosts=es_hosts, embedding_model=embedding_model)
        elif store_type == "qdrant":
            return QdrantVectorStore(embedding_model=embedding_model, url=qdrant_url)
        elif store_type == "pgvector":
            return PgVectorStore(
                connection_string=pg_connection_string,
                async_connection_string=pg_async_connection_string,
                embedding_model=embedding_model,
            )
        else:
            raise ValueError(f"Unknown store type: {store_type}")


# ==================== Sample Data Generator ====================


class SampleDataGenerator:
    """Generator for sample test data."""

    @staticmethod
    def create_sample_nodes(workspace_id: str, prefix: str = "") -> List[VectorNode]:
        """Create sample VectorNode instances for testing.

        Args:
            workspace_id: The workspace ID to assign to nodes
            prefix: Optional prefix for unique_id to avoid conflicts

        Returns:
            List[VectorNode]: List of sample nodes
        """
        id_prefix = f"{prefix}_" if prefix else ""
        return [
            VectorNode(
                unique_id=f"{id_prefix}node1",
                workspace_id=workspace_id,
                content="Artificial intelligence is a technology that simulates human intelligence.",
                metadata={
                    "node_type": "tech",
                    "category": "AI",
                },
            ),
            VectorNode(
                unique_id=f"{id_prefix}node2",
                workspace_id=workspace_id,
                content="Machine learning is a subset of artificial intelligence.",
                metadata={
                    "node_type": "tech",
                    "category": "ML",
                },
            ),
            VectorNode(
                unique_id=f"{id_prefix}node3",
                workspace_id=workspace_id,
                content="Machine learning is a subset of artificial intelligence.",
                metadata={
                    "node_type": "tech_new",
                    "category": "ML",
                },
            ),
            VectorNode(
                unique_id=f"{id_prefix}node4",
                workspace_id=workspace_id,
                content="I love eating delicious seafood, especially fresh fish.",
                metadata={
                    "node_type": "food",
                    "category": "preference",
                },
            ),
            VectorNode(
                unique_id=f"{id_prefix}node5",
                workspace_id=workspace_id,
                content="Deep learning uses neural networks with multiple layers.",
                metadata={
                    "node_type": "tech",
                    "category": "DL",
                },
            ),
        ]


# ==================== Base Test Class ====================


class BaseVectorStoreTest(ABC):
    """Abstract base class for vector store tests."""

    def __init__(
        self,
        store_type: STORE_TYPES,
        workspace_prefix: str = "test",
    ):
        """Initialize the test class.

        Args:
            store_type: Type of vector store to test
            workspace_prefix: Prefix for workspace IDs
        """
        self.store_type = store_type
        self.workspace_prefix = workspace_prefix
        self.embedding_model = OpenAICompatibleEmbeddingModel(
            dimensions=64,
            model_name="text-embedding-v4",
        )
        self.store_dir = f"./{store_type}_test_vector_store"
        self.client: BaseVectorStore = None

    def _get_workspace_id(self, suffix: str = "") -> str:
        """Generate a workspace ID with the configured prefix."""
        base_id = f"{self.workspace_prefix}_{self.store_type}_workspace"
        return f"{base_id}_{suffix}" if suffix else base_id

    @abstractmethod
    def run_all_tests(self):
        """Run all tests. Must be implemented by subclasses."""


# ==================== Synchronous Test Class ====================


class SyncVectorStoreTest(BaseVectorStoreTest):
    """Synchronous test class for vector stores."""

    def __init__(
        self,
        store_type: STORE_TYPES,
        workspace_prefix: str = "sync",
    ):
        super().__init__(store_type, workspace_prefix)
        self.client = VectorStoreFactory.create(
            store_type=store_type,
            embedding_model=self.embedding_model,
            store_dir=self.store_dir,
        )

    def test_create_workspace(self) -> str:
        """Test workspace creation."""
        logger.info("=" * 20 + " CREATE WORKSPACE TEST " + "=" * 20)
        workspace_id = self._get_workspace_id()

        # Clean up if exists
        if self.client.exist_workspace(workspace_id):
            self.client.delete_workspace(workspace_id)

        self.client.create_workspace(workspace_id)
        assert self.client.exist_workspace(workspace_id), "Workspace should exist after creation"
        logger.info(f"Created workspace: {workspace_id}")
        return workspace_id

    def test_insert(self, workspace_id: str) -> List[VectorNode]:
        """Test node insertion."""
        logger.info("=" * 20 + " INSERT TEST " + "=" * 20)
        sample_nodes = SampleDataGenerator.create_sample_nodes(workspace_id, self.workspace_prefix)
        self.client.insert(sample_nodes, workspace_id)
        logger.info(f"Inserted {len(sample_nodes)} nodes")
        return sample_nodes

    def test_search(self, workspace_id: str):
        """Test vector search."""
        logger.info("=" * 20 + " SEARCH TEST " + "=" * 20)
        results = self.client.search(
            "What is artificial intelligence?",
            workspace_id=workspace_id,
            top_k=3,
        )
        logger.info(f"Search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Result {i}: {r.model_dump(exclude={'vector'})}")
        assert len(results) > 0, "Search should return results"

    def test_search_with_filter(self, workspace_id: str):
        """Test vector search with filter."""
        logger.info("=" * 20 + " FILTER SEARCH TEST " + "=" * 20)
        filter_dict = {"metadata.node_type": ["tech", "tech_new"]}
        results = self.client.search(
            "What is artificial intelligence?",
            workspace_id=workspace_id,
            top_k=5,
            filter_dict=filter_dict,
        )
        logger.info(f"Filtered search returned {len(results)} results (node_type in [tech, tech_new])")
        for i, r in enumerate(results, 1):
            logger.info(f"Filtered Result {i}: {r.model_dump(exclude={'vector'})}")
            assert r.metadata.get("node_type") in [
                "tech",
                "tech_new",
            ], "All results should have node_type in [tech, tech_new]"

    def test_search_with_id(self, workspace_id: str):
        """Test vector search by unique_id with empty query."""
        logger.info("=" * 20 + " SEARCH BY ID TEST " + "=" * 20)
        target_unique_id = f"{self.workspace_prefix}_node1"
        filter_dict = {"unique_id": target_unique_id}
        results = self.client.search(
            "",
            workspace_id=workspace_id,
            top_k=1,
            filter_dict=filter_dict,
        )
        logger.info(f"Search by ID returned {len(results)} results")
        assert len(results) == 1, "Should return exactly one result"
        assert results[0].unique_id == target_unique_id, f"Result should have unique_id={target_unique_id}"
        logger.info(f"Found node: {results[0].model_dump(exclude={'vector'})}")

    def test_update(self, workspace_id: str):
        """Test node update (insert with existing unique_id)."""
        logger.info("=" * 20 + " UPDATE TEST " + "=" * 20)
        updated_node = VectorNode(
            unique_id=f"{self.workspace_prefix}_node2",
            workspace_id=workspace_id,
            content="Machine learning is a powerful subset of AI that learns from data.",
            metadata={
                "node_type": "tech",
                "category": "ML",
                "updated": True,
            },
        )
        self.client.insert(updated_node, workspace_id)

        # Search to verify update
        results = self.client.search("machine learning", workspace_id=workspace_id, top_k=2)
        logger.info(f"After update, search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Updated Result {i}: {r.model_dump(exclude={'vector'})}")

    def test_delete(self, workspace_id: str):
        """Test node deletion."""
        logger.info("=" * 20 + " DELETE TEST " + "=" * 20)
        node_to_delete = f"{self.workspace_prefix}_node3"
        self.client.delete(node_to_delete, workspace_id=workspace_id)

        # Search for deleted content
        results = self.client.search("food fish", workspace_id=workspace_id, top_k=5)
        logger.info(f"After deletion, found {len(results)} food-related results")

    def test_list_workspace_nodes(self, workspace_id: str):
        """Test listing all nodes in a workspace."""
        logger.info("=" * 20 + " LIST WORKSPACE NODES TEST " + "=" * 20)
        nodes = self.client.list_workspace_nodes(workspace_id)
        logger.info(f"Workspace has {len(nodes)} nodes")
        for i, node in enumerate(nodes, 1):
            logger.info(f"Node {i}: unique_id={node.unique_id}, content={node.content[:50]}...")

    def test_dump_workspace(self, workspace_id: str):
        """Test dumping workspace to disk."""
        logger.info("=" * 20 + " DUMP WORKSPACE TEST " + "=" * 20)
        dump_result = self.client.dump_workspace(workspace_id, path=self.store_dir)
        logger.info(f"Dumped {dump_result.get('size', 0)} nodes to disk")
        return dump_result

    def test_load_workspace(self, workspace_id: str):
        """Test loading workspace from disk."""
        logger.info("=" * 20 + " LOAD WORKSPACE TEST " + "=" * 20)

        # Use a separate dump path to avoid being deleted by delete_workspace
        dump_path = f"{self.store_dir}_dump"

        # First dump, then delete from memory, then load
        self.client.dump_workspace(workspace_id, path=dump_path)
        self.client.delete_workspace(workspace_id)
        logger.info(f"Deleted workspace from memory, exists: {self.client.exist_workspace(workspace_id)}")

        load_result = self.client.load_workspace(workspace_id, path=dump_path)
        logger.info(f"Loaded {load_result.get('size', 0)} nodes from disk")

        # Verify loaded data
        results = self.client.search("AI technology", workspace_id=workspace_id, top_k=3)
        logger.info(f"After load, search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Loaded Result {i}: {r.model_dump(exclude={'vector'})}")

    def test_copy_workspace(self, workspace_id: str):
        """Test copying workspace."""
        logger.info("=" * 20 + " COPY WORKSPACE TEST " + "=" * 20)
        copy_workspace_id = self._get_workspace_id("copy")

        # Clean up if exists
        if self.client.exist_workspace(copy_workspace_id):
            self.client.delete_workspace(copy_workspace_id)

        copy_result = self.client.copy_workspace(workspace_id, copy_workspace_id)
        logger.info(f"Copied {copy_result.get('size', 0)} nodes to new workspace")

        # Search in copied workspace
        results = self.client.search("AI technology", workspace_id=copy_workspace_id, top_k=2)
        logger.info(f"Copy workspace search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Copy Result {i}: {r.model_dump(exclude={'vector'})}")

        # Clean up copy
        self.client.delete_workspace(copy_workspace_id)

    def test_list_workspace(self):
        """Test listing all workspaces."""
        logger.info("=" * 20 + " LIST WORKSPACE TEST " + "=" * 20)
        workspaces = self.client.list_workspace()
        logger.info(f"Found {len(workspaces)} workspaces: {workspaces}")

    def test_exist_workspace(self, workspace_id: str):
        """Test workspace existence check."""
        logger.info("=" * 20 + " EXIST WORKSPACE TEST " + "=" * 20)
        exists = self.client.exist_workspace(workspace_id)
        logger.info(f"Workspace {workspace_id} exists: {exists}")
        assert exists, "Workspace should exist"

    def test_delete_workspace(self, workspace_id: str):
        """Test workspace deletion."""
        logger.info("=" * 20 + " DELETE WORKSPACE TEST " + "=" * 20)
        self.client.delete_workspace(workspace_id)
        exists = self.client.exist_workspace(workspace_id)
        logger.info(f"After deletion, workspace exists: {exists}")
        assert not exists, "Workspace should not exist after deletion"

    def cleanup(self, workspace_id: str):
        """Clean up test resources."""
        logger.info("=" * 20 + " CLEANUP " + "=" * 20)
        if self.client.exist_workspace(workspace_id):
            self.client.delete_workspace(workspace_id)
        copy_workspace_id = self._get_workspace_id("copy")
        if self.client.exist_workspace(copy_workspace_id):
            self.client.delete_workspace(copy_workspace_id)
        self.client.close()
        logger.info("Cleanup completed")

    def run_all_tests(self):
        """Run all synchronous tests."""
        logger.info("=" * 50 + f" SYNC {self.store_type.upper()} TESTS " + "=" * 50)

        workspace_id = self.test_create_workspace()
        try:
            self.test_insert(workspace_id)
            self.test_search(workspace_id)
            self.test_search_with_filter(workspace_id)
            self.test_search_with_id(workspace_id)
            self.test_update(workspace_id)
            self.test_delete(workspace_id)
            self.test_list_workspace_nodes(workspace_id)
            self.test_exist_workspace(workspace_id)
            self.test_list_workspace()
            self.test_copy_workspace(workspace_id)
            self.test_dump_workspace(workspace_id)
            self.test_load_workspace(workspace_id)
        finally:
            self.cleanup(workspace_id)


# ==================== Asynchronous Test Class ====================


class AsyncVectorStoreTest(BaseVectorStoreTest):
    """Asynchronous test class for vector stores."""

    def __init__(
        self,
        store_type: STORE_TYPES,
        workspace_prefix: str = "async",
    ):
        super().__init__(store_type, workspace_prefix)
        self.client = VectorStoreFactory.create(
            store_type=store_type,
            embedding_model=self.embedding_model,
            store_dir=self.store_dir,
        )

    async def test_create_workspace(self) -> str:
        """Test async workspace creation."""
        logger.info("ASYNC - " + "=" * 20 + " CREATE WORKSPACE TEST " + "=" * 20)
        workspace_id = self._get_workspace_id()

        # Clean up if exists
        if await self.client.async_exist_workspace(workspace_id):
            await self.client.async_delete_workspace(workspace_id)

        await self.client.async_create_workspace(workspace_id)
        assert await self.client.async_exist_workspace(workspace_id), "Workspace should exist after creation"
        logger.info(f"Created workspace: {workspace_id}")
        return workspace_id

    async def test_insert(self, workspace_id: str) -> List[VectorNode]:
        """Test async node insertion."""
        logger.info("ASYNC - " + "=" * 20 + " INSERT TEST " + "=" * 20)
        sample_nodes = SampleDataGenerator.create_sample_nodes(workspace_id, self.workspace_prefix)
        await self.client.async_insert(sample_nodes, workspace_id)
        logger.info(f"Inserted {len(sample_nodes)} nodes")
        return sample_nodes

    async def test_search(self, workspace_id: str):
        """Test async vector search."""
        logger.info("ASYNC - " + "=" * 20 + " SEARCH TEST " + "=" * 20)
        results = await self.client.async_search(
            "What is artificial intelligence?",
            workspace_id=workspace_id,
            top_k=3,
        )
        logger.info(f"Search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Result {i}: {r.model_dump(exclude={'vector'})}")
        assert len(results) > 0, "Search should return results"

    async def test_search_with_filter(self, workspace_id: str):
        """Test async vector search with filter."""
        logger.info("ASYNC - " + "=" * 20 + " FILTER SEARCH TEST " + "=" * 20)
        filter_dict = {"metadata.node_type": ["tech", "tech_new"]}
        results = await self.client.async_search(
            "What is artificial intelligence?",
            workspace_id=workspace_id,
            top_k=5,
            filter_dict=filter_dict,
        )
        logger.info(f"Filtered search returned {len(results)} results (node_type in [tech, tech_new])")
        for i, r in enumerate(results, 1):
            logger.info(f"Filtered Result {i}: {r.model_dump(exclude={'vector'})}")
            assert r.metadata.get("node_type") in [
                "tech",
                "tech_new",
            ], "All results should have node_type in [tech, tech_new]"

    async def test_search_with_id(self, workspace_id: str):
        """Test async vector search by unique_id with empty query."""
        logger.info("ASYNC - " + "=" * 20 + " SEARCH BY ID TEST " + "=" * 20)
        target_unique_id = f"{self.workspace_prefix}_node1"
        filter_dict = {"unique_id": target_unique_id}
        results = await self.client.async_search(
            "",
            workspace_id=workspace_id,
            top_k=1,
            filter_dict=filter_dict,
        )
        logger.info(f"Search by ID returned {len(results)} results")
        assert len(results) == 1, "Should return exactly one result"
        assert results[0].unique_id == target_unique_id, f"Result should have unique_id={target_unique_id}"
        logger.info(f"Found node: {results[0].model_dump(exclude={'vector'})}")

    async def test_update(self, workspace_id: str):
        """Test async node update (insert with existing unique_id)."""
        logger.info("ASYNC - " + "=" * 20 + " UPDATE TEST " + "=" * 20)
        updated_node = VectorNode(
            unique_id=f"{self.workspace_prefix}_node2",
            workspace_id=workspace_id,
            content="Machine learning is a powerful subset of AI that learns from data.",
            metadata={
                "node_type": "tech",
                "category": "ML",
                "updated": True,
            },
        )
        await self.client.async_insert(updated_node, workspace_id)

        # Search to verify update
        results = await self.client.async_search("machine learning", workspace_id=workspace_id, top_k=2)
        logger.info(f"After update, search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Updated Result {i}: {r.model_dump(exclude={'vector'})}")

    async def test_delete(self, workspace_id: str):
        """Test async node deletion."""
        logger.info("ASYNC - " + "=" * 20 + " DELETE TEST " + "=" * 20)
        node_to_delete = f"{self.workspace_prefix}_node3"
        await self.client.async_delete(node_to_delete, workspace_id=workspace_id)

        # Search for deleted content
        results = await self.client.async_search("food fish", workspace_id=workspace_id, top_k=5)
        logger.info(f"After deletion, found {len(results)} food-related results")

    async def test_list_workspace_nodes(self, workspace_id: str):
        """Test async listing all nodes in a workspace."""
        logger.info("ASYNC - " + "=" * 20 + " LIST WORKSPACE NODES TEST " + "=" * 20)
        nodes = await self.client.async_list_workspace_nodes(workspace_id)
        logger.info(f"Workspace has {len(nodes)} nodes")
        for i, node in enumerate(nodes, 1):
            logger.info(f"Node {i}: unique_id={node.unique_id}, content={node.content[:50]}...")

    async def test_dump_workspace(self, workspace_id: str):
        """Test async dumping workspace to disk."""
        logger.info("ASYNC - " + "=" * 20 + " DUMP WORKSPACE TEST " + "=" * 20)
        dump_result = await self.client.async_dump_workspace(workspace_id, path=self.store_dir)
        logger.info(f"Dumped {dump_result.get('size', 0)} nodes to disk")
        return dump_result

    async def test_load_workspace(self, workspace_id: str):
        """Test async loading workspace from disk."""
        logger.info("ASYNC - " + "=" * 20 + " LOAD WORKSPACE TEST " + "=" * 20)

        # Use a separate dump path to avoid being deleted by delete_workspace
        dump_path = f"{self.store_dir}_dump"

        # First dump, then delete from memory, then load
        await self.client.async_dump_workspace(workspace_id, path=dump_path)
        await self.client.async_delete_workspace(workspace_id)
        logger.info(f"Deleted workspace from memory, exists: {await self.client.async_exist_workspace(workspace_id)}")

        load_result = await self.client.async_load_workspace(workspace_id, path=dump_path)
        logger.info(f"Loaded {load_result.get('size', 0)} nodes from disk")

        # Verify loaded data
        results = await self.client.async_search("AI technology", workspace_id=workspace_id, top_k=3)
        logger.info(f"After load, search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Loaded Result {i}: {r.model_dump(exclude={'vector'})}")

    async def test_copy_workspace(self, workspace_id: str):
        """Test async copying workspace."""
        logger.info("ASYNC - " + "=" * 20 + " COPY WORKSPACE TEST " + "=" * 20)
        copy_workspace_id = self._get_workspace_id("copy")

        # Clean up if exists
        if await self.client.async_exist_workspace(copy_workspace_id):
            await self.client.async_delete_workspace(copy_workspace_id)

        copy_result = await self.client.async_copy_workspace(workspace_id, copy_workspace_id)
        logger.info(f"Copied {copy_result.get('size', 0)} nodes to new workspace")

        # Search in copied workspace
        results = await self.client.async_search("AI technology", workspace_id=copy_workspace_id, top_k=2)
        logger.info(f"Copy workspace search returned {len(results)} results")
        for i, r in enumerate(results, 1):
            logger.info(f"Copy Result {i}: {r.model_dump(exclude={'vector'})}")

        # Clean up copy
        await self.client.async_delete_workspace(copy_workspace_id)

    async def test_list_workspace(self):
        """Test async listing all workspaces."""
        logger.info("ASYNC - " + "=" * 20 + " LIST WORKSPACE TEST " + "=" * 20)
        workspaces = await self.client.async_list_workspace()
        logger.info(f"Found {len(workspaces)} workspaces: {workspaces}")

    async def test_exist_workspace(self, workspace_id: str):
        """Test async workspace existence check."""
        logger.info("ASYNC - " + "=" * 20 + " EXIST WORKSPACE TEST " + "=" * 20)
        exists = await self.client.async_exist_workspace(workspace_id)
        logger.info(f"Workspace {workspace_id} exists: {exists}")
        assert exists, "Workspace should exist"

    async def test_delete_workspace(self, workspace_id: str):
        """Test async workspace deletion."""
        logger.info("ASYNC - " + "=" * 20 + " DELETE WORKSPACE TEST " + "=" * 20)
        await self.client.async_delete_workspace(workspace_id)
        exists = await self.client.async_exist_workspace(workspace_id)
        logger.info(f"After deletion, workspace exists: {exists}")
        assert not exists, "Workspace should not exist after deletion"

    async def cleanup(self, workspace_id: str):
        """Clean up test resources."""
        logger.info("ASYNC - " + "=" * 20 + " CLEANUP " + "=" * 20)
        if await self.client.async_exist_workspace(workspace_id):
            await self.client.async_delete_workspace(workspace_id)
        copy_workspace_id = self._get_workspace_id("copy")
        if await self.client.async_exist_workspace(copy_workspace_id):
            await self.client.async_delete_workspace(copy_workspace_id)
        await self.client.async_close()
        # Close the embedding model's async client to prevent "Event loop is closed" errors
        await self.embedding_model.async_close()
        logger.info("Async cleanup completed")

    async def _run_all_tests_async(self):
        """Run all asynchronous tests."""
        logger.info("=" * 50 + f" ASYNC {self.store_type.upper()} TESTS " + "=" * 50)

        workspace_id = await self.test_create_workspace()
        try:
            await self.test_insert(workspace_id)
            await self.test_search(workspace_id)
            await self.test_search_with_filter(workspace_id)
            await self.test_search_with_id(workspace_id)
            await self.test_update(workspace_id)
            await self.test_delete(workspace_id)
            await self.test_list_workspace_nodes(workspace_id)
            await self.test_exist_workspace(workspace_id)
            await self.test_list_workspace()
            await self.test_copy_workspace(workspace_id)
            await self.test_dump_workspace(workspace_id)
            await self.test_load_workspace(workspace_id)
        finally:
            await self.cleanup(workspace_id)

    def run_all_tests(self):
        """Run all asynchronous tests."""
        asyncio.run(self._run_all_tests_async())


# ==================== Test Runner ====================


def run_tests(
    store_types: List[str],
):
    """Run vector store tests (both sync and async).

    Args:
        store_types: List of store types to test (e.g., ["memory", "local"])
    """
    for st in store_types:
        logger.info(f"\n{'=' * 60}\nTesting {st.upper()} VectorStore\n{'=' * 60}")
        try:
            # Run sync tests
            sync_test = SyncVectorStoreTest(store_type=st)
            sync_test.run_all_tests()

            # Run async tests
            async_test = AsyncVectorStoreTest(store_type=st)
            async_test.run_all_tests()
        except Exception as e:
            logger.error(f"Failed to test {st}: {e}")
            if len(store_types) == 1:
                raise


def delete_test_files():
    """Delete all test-generated files and directories.

    This function removes all directories that match test patterns:
    - *_test_vector_store
    - *_test_vector_store_dump
    - chroma_test_db
    """
    # Get the project root directory (parent of tests/)
    project_root = Path(__file__).parent.parent

    # Patterns for test directories to delete
    test_patterns = [
        "*_test_vector_store",
        "*_test_vector_store_dump",
        "chroma_test_db",
    ]

    deleted_count = 0

    for pattern in test_patterns:
        for path in project_root.glob(pattern):
            if path.is_dir():
                try:
                    shutil.rmtree(path)
                    logger.info(f"Deleted directory: {path}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {path}: {e}")
            elif path.is_file():
                try:
                    path.unlink()
                    logger.info(f"Deleted file: {path}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete {path}: {e}")

    if deleted_count == 0:
        logger.info("No test files/directories found to delete.")
    else:
        logger.info(f"Successfully deleted {deleted_count} test files/directories.")


def print_usage():
    """Print usage information."""
    print(__doc__)
    print("\nAvailable store types:")
    for store_type in VectorStoreFactory.get_all_store_types():
        print(f"  - {store_type}")
    print("\nOther commands:")
    print("  - delete: Delete all test-generated files and directories")


if __name__ == "__main__":
    args = sys.argv[1:]
    valid_store_types = VectorStoreFactory.get_all_store_types()

    if not args or args[0] in ("-h", "--help"):
        print_usage()
        sys.exit(0)

    if args[0] == "--all":
        # Test all vector stores
        run_tests(store_types=valid_store_types)
    elif args[0] == "delete":
        # Delete all test-generated files
        delete_test_files()
    elif args[0] in valid_store_types:
        # Test specific vector store
        run_tests(store_types=[args[0]])
    else:
        print(f"Unknown argument: {args[0]}")
        print_usage()
        sys.exit(1)
