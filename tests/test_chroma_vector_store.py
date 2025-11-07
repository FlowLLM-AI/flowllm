"""Test script for ChromaVectorStore.

This script provides test functions for both synchronous and asynchronous
vector store operations. It can be run directly with: python test_chroma_vector_store.py

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint
"""

import asyncio
import os
import shutil

from loguru import logger

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.schema.vector_node import VectorNode
from flowllm.core.utils import load_env
from flowllm.core.vector_store.chroma_vector_store import ChromaVectorStore

load_env()


def main():
    """
    Test the ChromaVectorStore with synchronous operations.

    This function demonstrates basic operations including create, insert, search,
    filtering, update (delete + insert), dump_workspace, load_workspace, and workspace management.
    """
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "chroma_test_index"
    store_dir = os.path.abspath("./chroma_test_db")

    # Clean up any existing database directory
    if os.path.exists(store_dir):
        shutil.rmtree(store_dir)

    chroma_store = ChromaVectorStore(
        embedding_model=embedding_model,
        store_dir=store_dir,
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
                "category": "tech",
            },
        ),
        VectorNode(
            unique_id="node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
                "category": "tech",
            },
        ),
        VectorNode(
            unique_id="node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
                "category": "food",
            },
        ),
        VectorNode(
            unique_id="node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
                "category": "food",
            },
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
            "updated": True,
        },
    )
    chroma_store.delete(node2_update.unique_id, workspace_id=workspace_id)
    chroma_store.insert(node2_update, workspace_id=workspace_id)

    logger.info("Updated Result:")
    results = chroma_store.search("fish?", top_k=10, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test dump_workspace
    dump_result = chroma_store.dump_workspace(workspace_id=workspace_id)
    logger.info(f"Dump result: {dump_result}")

    # Test load_workspace: delete workspace and reload from dump
    logger.info("=" * 20 + " LOAD TEST " + "=" * 20)
    chroma_store.delete_workspace(workspace_id=workspace_id)
    logger.info(f"Workspace deleted, exist_workspace: {chroma_store.exist_workspace(workspace_id)}")

    # Load workspace back
    load_result = chroma_store.load_workspace(workspace_id)
    logger.info(f"Load result: {load_result}")

    # Verify data is restored by searching
    results = chroma_store.search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"After load, search returned {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    chroma_store.delete_workspace(workspace_id=workspace_id)

    # Clean up the store directory
    if os.path.exists(store_dir):
        shutil.rmtree(store_dir)


async def async_main():
    """
    Test the ChromaVectorStore with asynchronous operations.

    This function demonstrates async operations including async_create_workspace,
    async_insert, async_search, async_delete, async_dump_workspace, and
    async_load_workspace for better performance in async applications.
    """
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "chroma_async_test_index"
    store_dir = os.path.abspath("./async_chroma_test_db")

    # Clean up any existing database directory
    if os.path.exists(store_dir):
        shutil.rmtree(store_dir)

    chroma_store = ChromaVectorStore(
        embedding_model=embedding_model,
        store_dir=store_dir,
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
                "category": "tech",
            },
        ),
        VectorNode(
            unique_id="async_node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
                "category": "tech",
            },
        ),
        VectorNode(
            unique_id="async_node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
                "category": "food",
            },
        ),
        VectorNode(
            unique_id="async_node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
                "category": "food",
            },
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
            "updated": True,
        },
    )
    await chroma_store.async_delete(node2_update.unique_id, workspace_id=workspace_id)
    await chroma_store.async_insert(node2_update, workspace_id=workspace_id)

    logger.info("ASYNC Updated Result:")
    results = await chroma_store.async_search("fish?", top_k=10, workspace_id=workspace_id)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async_dump_workspace
    dump_result = await chroma_store.async_dump_workspace(workspace_id=workspace_id)
    logger.info(f"Async dump result: {dump_result}")

    # Test async_load_workspace: delete workspace and reload from dump
    logger.info("ASYNC LOAD TEST - " + "=" * 20)
    await chroma_store.async_delete_workspace(workspace_id=workspace_id)
    logger.info(f"Workspace deleted, exist_workspace: {await chroma_store.async_exist_workspace(workspace_id)}")

    # Load workspace back
    load_result = await chroma_store.async_load_workspace(workspace_id)
    logger.info(f"Async load result: {load_result}")

    # Verify data is restored by searching
    results = await chroma_store.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"After async load, search returned {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Clean up
    await chroma_store.async_delete_workspace(workspace_id=workspace_id)

    # Clean up the store directory
    if os.path.exists(store_dir):
        shutil.rmtree(store_dir)


if __name__ == "__main__":
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    asyncio.run(async_main())
