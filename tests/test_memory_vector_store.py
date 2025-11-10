"""Test script for MemoryVectorStore.

This script provides test functions for both synchronous and asynchronous
vector store operations. It can be run directly with: python test_memory_vector_store.py

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint
"""

import asyncio

from loguru import logger

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.schema.vector_node import VectorNode
from flowllm.core.utils import load_env
from flowllm.core.vector_store.memory_vector_store import MemoryVectorStore

load_env()


def main():
    """Test the MemoryVectorStore with synchronous operations including dump_workspace and load_workspace"""
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "memory_test_workspace"
    client = MemoryVectorStore(embedding_model=embedding_model)

    # Clean up and create workspace
    if client.exist_workspace(workspace_id):
        client.delete_workspace(workspace_id)
    client.create_workspace(workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="memory_node1",
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "tech",
                "category": "AI",
            },
        ),
        VectorNode(
            unique_id="memory_node2",
            workspace_id=workspace_id,
            content="Machine learning is a subset of artificial intelligence.",
            metadata={
                "node_type": "tech",
                "category": "ML",
            },
        ),
        VectorNode(
            unique_id="memory_node3",
            workspace_id=workspace_id,
            content="I love eating delicious seafood, especially fresh fish.",
            metadata={
                "node_type": "food",
                "category": "preference",
            },
        ),
        VectorNode(
            unique_id="memory_node4",
            workspace_id=workspace_id,
            content="Deep learning uses neural networks with multiple layers.",
            metadata={
                "node_type": "tech",
                "category": "DL",
            },
        ),
    ]

    # Test insert
    logger.info("Testing insert...")
    client.insert(sample_nodes, workspace_id)

    # Test search
    logger.info("=" * 20 + " SEARCH TEST " + "=" * 20)
    results = client.search("What is artificial intelligence?", workspace_id=workspace_id, top_k=3)
    for i, r in enumerate(results, 1):
        logger.info(f"Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test filter_dict
    logger.info("=" * 20 + " FILTER TEST " + "=" * 20)
    filter_dict = {"node_type": "tech"}
    results = client.search(
        "What is artificial intelligence?",
        workspace_id=workspace_id,
        top_k=5,
        filter_dict=filter_dict,
    )
    logger.info(f"Filtered results (node_type=tech): {len(results)} results")
    for i, r in enumerate(results, 1):
        logger.info(f"Filtered Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test update (insert existing node with same unique_id)
    logger.info("=" * 20 + " UPDATE TEST " + "=" * 20)
    updated_node = VectorNode(
        unique_id="memory_node2",  # Same ID as existing node
        workspace_id=workspace_id,
        content="Machine learning is a powerful subset of AI that learns from data.",
        metadata={
            "node_type": "tech",
            "category": "ML",
            "updated": True,
        },
    )
    client.insert(updated_node, workspace_id)

    # Search again to see updated content
    results = client.search("machine learning", workspace_id=workspace_id, top_k=2)
    for i, r in enumerate(results, 1):
        logger.info(f"Updated Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test delete
    logger.info("=" * 20 + " DELETE TEST " + "=" * 20)
    client.delete("memory_node3", workspace_id=workspace_id)

    # Search for food-related content (should return fewer results)
    results = client.search("food fish", workspace_id=workspace_id, top_k=5)
    logger.info(f"After deletion, found {len(results)} food-related results")

    # Test dump to disk
    logger.info("=" * 20 + " DUMP TEST " + "=" * 20)
    dump_result = client.dump_workspace(workspace_id)
    logger.info(f"Dumped {dump_result['size']} nodes to disk")

    # Test load from disk (first delete from memory, then load)
    logger.info("=" * 20 + " LOAD TEST " + "=" * 20)
    client.delete_workspace(workspace_id)  # Clear from memory
    logger.info(f"Workspace deleted from memory, exist_workspace: {client.exist_workspace(workspace_id)}")

    load_result = client.load_workspace(workspace_id, path=client.store_path)
    logger.info(f"Loaded {load_result['size']} nodes from disk")

    # Verify loaded data
    results = client.search("AI technology", workspace_id=workspace_id, top_k=3)
    logger.info(f"After load, search returned {len(results)} results")
    for i, r in enumerate(results, 1):
        logger.info(f"Loaded Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test copy workspace
    logger.info("=" * 20 + " COPY TEST " + "=" * 20)
    copy_workspace_id = "memory_copy_workspace"
    copy_result = client.copy_workspace(workspace_id, copy_workspace_id)
    logger.info(f"Copied {copy_result['size']} nodes to new workspace")

    # Search in copied workspace
    results = client.search("AI technology", workspace_id=copy_workspace_id, top_k=2)
    for i, r in enumerate(results, 1):
        logger.info(f"Copy Result {i}: {r.model_dump(exclude={'vector'})}")

    # Clean up
    client.delete_workspace(workspace_id)
    client.delete_workspace(copy_workspace_id)
    logger.info("Cleanup completed")


async def async_main():
    """Test the MemoryVectorStore with asynchronous operations"""
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "async_memory_test_workspace"
    client = MemoryVectorStore(embedding_model=embedding_model, store_dir="./async_memory_vector_store")

    # Clean up and create workspace
    if await client.async_exist_workspace(workspace_id):
        await client.async_delete_workspace(workspace_id)
    await client.async_create_workspace(workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="async_memory_node1",
            workspace_id=workspace_id,
            content="Quantum computing represents the future of computational power.",
            metadata={
                "node_type": "tech",
                "category": "quantum",
            },
        ),
        VectorNode(
            unique_id="async_memory_node2",
            workspace_id=workspace_id,
            content="Blockchain technology enables decentralized applications.",
            metadata={
                "node_type": "tech",
                "category": "blockchain",
            },
        ),
        VectorNode(
            unique_id="async_memory_node3",
            workspace_id=workspace_id,
            content="Cloud computing provides scalable infrastructure solutions.",
            metadata={
                "node_type": "tech",
                "category": "cloud",
            },
        ),
        VectorNode(
            unique_id="async_memory_node4",
            workspace_id=workspace_id,
            content="Pizza is my favorite Italian food with cheese and tomatoes.",
            metadata={
                "node_type": "food",
                "category": "italian",
            },
        ),
    ]

    # Test async insert
    logger.info("ASYNC TEST - Testing insert...")
    await client.async_insert(sample_nodes, workspace_id)

    # Test async search
    logger.info("ASYNC TEST - " + "=" * 20 + " SEARCH TEST " + "=" * 20)
    results = await client.async_search("What is quantum computing?", workspace_id=workspace_id, top_k=3)
    for i, r in enumerate(results, 1):
        logger.info(f"Async Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test async update
    logger.info("ASYNC TEST - " + "=" * 20 + " UPDATE TEST " + "=" * 20)
    updated_node = VectorNode(
        unique_id="async_memory_node2",  # Same ID as existing node
        workspace_id=workspace_id,
        content="Blockchain is a revolutionary distributed ledger technology for secure transactions.",
        metadata={
            "node_type": "tech",
            "category": "blockchain",
            "updated": True,
            "version": "2.0",
        },
    )
    await client.async_insert(updated_node, workspace_id)

    # Search again to see updated content
    results = await client.async_search("blockchain distributed", workspace_id=workspace_id, top_k=2)
    for i, r in enumerate(results, 1):
        logger.info(f"Async Updated Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test async delete
    logger.info("ASYNC TEST - " + "=" * 20 + " DELETE TEST " + "=" * 20)
    await client.async_delete("async_memory_node4", workspace_id=workspace_id)

    # Search for food-related content (should return no results)
    results = await client.async_search("pizza food", workspace_id=workspace_id, top_k=5)
    logger.info(f"After async deletion, found {len(results)} food-related results")

    # Test async dump to disk
    logger.info("ASYNC TEST - " + "=" * 20 + " DUMP TEST " + "=" * 20)
    dump_result = await client.async_dump_workspace(workspace_id)
    logger.info(f"Async dumped {dump_result['size']} nodes to disk")

    # Test load from disk (first delete from memory, then load)
    logger.info("ASYNC TEST - " + "=" * 20 + " LOAD TEST " + "=" * 20)
    await client.async_delete_workspace(workspace_id)  # Clear from memory
    load_result = await client.async_load_workspace(workspace_id, path=client.store_path)
    logger.info(f"Async loaded {load_result['size']} nodes from disk")

    # Verify loaded data
    results = await client.async_search("quantum technology", workspace_id=workspace_id, top_k=3)
    for i, r in enumerate(results, 1):
        logger.info(f"Loaded Result {i}: {r.model_dump(exclude={'vector'})}")

    # Test async copy workspace
    logger.info("ASYNC TEST - " + "=" * 20 + " COPY TEST " + "=" * 20)
    copy_workspace_id = "async_memory_copy_workspace"
    copy_result = await client.async_copy_workspace(workspace_id, copy_workspace_id)
    logger.info(f"Async copied {copy_result['size']} nodes to new workspace")

    # Search in copied workspace
    results = await client.async_search("computing technology", workspace_id=copy_workspace_id, top_k=2)
    for i, r in enumerate(results, 1):
        logger.info(f"Async Copy Result {i}: {r.model_dump(exclude={'vector'})}")

    # Final cleanup
    await client.async_delete_workspace(workspace_id)
    await client.async_delete_workspace(copy_workspace_id)
    logger.info("Async cleanup completed")


if __name__ == "__main__":
    # Run sync test
    logger.info("=" * 50 + " SYNC TESTS " + "=" * 50)
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    asyncio.run(async_main())
