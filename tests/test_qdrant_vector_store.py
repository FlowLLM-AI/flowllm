"""Test script for QdrantVectorStore.

This script provides test functions for both synchronous and asynchronous
vector store operations. It can be run directly with: python test_qdrant_vector_store.py

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint

Also requires Qdrant server to be running. Can be configured via:
- FLOW_QDRANT_HOST: Qdrant host (default: localhost)
- FLOW_QDRANT_PORT: Qdrant port (default: 6333)
- Or specify url directly in the test code
"""

import asyncio

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.schema.vector_node import VectorNode
from flowllm.core.utils import load_env
from flowllm.core.vector_store.qdrant_vector_store import QdrantVectorStore
from loguru import logger

load_env()


def main():
    """
    Test the QdrantVectorStore with synchronous operations.

    This function demonstrates basic operations including create, insert, search,
    filtering, update (delete + insert), and workspace management.
    """
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "qdrant_rag_nodes_index"

    # Option 1: Use default localhost:6333
    qdrant = QdrantVectorStore(embedding_model=embedding_model, url="http://47.237.23.175:6333")

    # Option 2: Specify host and port
    # qdrant = QdrantVectorStore(embedding_model=embedding_model, host="localhost", port=6333)

    # Option 3: Use URL (e.g., for Qdrant Cloud)
    # qdrant = QdrantVectorStore(
    #     embedding_model=embedding_model,
    #     url="https://your-cluster.qdrant.io:6333",
    #     api_key="your-api-key"
    # )

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
    """
    Test the QdrantVectorStore with asynchronous operations.

    This function demonstrates async operations including async_create_workspace,
    async_insert, async_search, async_delete for better performance in
    async applications.
    """
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

