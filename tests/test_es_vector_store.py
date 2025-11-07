"""Test script for EsVectorStore.

This script provides test functions for both synchronous and asynchronous
vector store operations. It can be run directly with: python test_es_vector_store.py

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint
- FLOW_ES_HOSTS: Elasticsearch host URL (optional, defaults to http://localhost:9200)
"""

import asyncio

from loguru import logger

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.schema.vector_node import VectorNode
from flowllm.core.utils import load_env
from flowllm.core.vector_store.es_vector_store import EsVectorStore

load_env()


def main():
    """
    Test the EsVectorStore with synchronous operations.

    This function demonstrates basic operations including create, insert, search,
    filtering, update (delete + insert), dump_workspace, load_workspace, and workspace management.
    """
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

    es.insert(sample_nodes, workspace_id=workspace_id, refresh=True)

    logger.info("=" * 20 + " FILTER TEST " + "=" * 20)
    filter_dict = {"node_type": "n1"}
    results = es.search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
    logger.info(f"Filtered results (node_type=n1): {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    logger.info("=" * 20 + " UNFILTERED TEST " + "=" * 20)
    results = es.search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"Unfiltered results: {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test dump_workspace
    dump_result = es.dump_workspace(workspace_id=workspace_id)
    logger.info(f"Dump result: {dump_result}")

    # Test load_workspace: delete workspace and reload from dump
    logger.info("=" * 20 + " LOAD TEST " + "=" * 20)
    es.delete_workspace(workspace_id=workspace_id)
    logger.info(f"Workspace deleted, exist_workspace: {es.exist_workspace(workspace_id)}")

    # Load workspace back
    load_result = es.load_workspace(workspace_id)
    logger.info(f"Load result: {load_result}")

    # Verify data is restored by searching
    results = es.search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"After load, search returned {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    es.delete_workspace(workspace_id=workspace_id)
    es.close()


async def async_main():
    """
    Test the EsVectorStore with asynchronous operations.

    This function demonstrates async operations including async_create_workspace,
    async_insert, async_search, async_delete, async_dump_workspace, and
    async_load_workspace for better performance in async applications.
    """
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "async_rag_nodes_index"
    hosts = "http://11.160.132.46:8200"

    # Use async context manager to ensure proper cleanup
    es = EsVectorStore(hosts=hosts, embedding_model=embedding_model)
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
            },
        ),
        VectorNode(
            unique_id="async_es_node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            unique_id="async_es_node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
            },
        ),
        VectorNode(
            unique_id="async_es_node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
            },
        ),
    ]

    # Test async insert
    await es.async_insert(sample_nodes, workspace_id=workspace_id, refresh=True)

    logger.info("ASYNC TEST - " + "=" * 20)
    # Test async search with filter
    filter_dict = {"node_type": "n1"}
    results = await es.async_search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
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
            "updated": True,
        },
    )
    await es.async_delete(node2_update.unique_id, workspace_id=workspace_id, refresh=True)
    await es.async_insert(node2_update, workspace_id=workspace_id, refresh=True)

    logger.info("ASYNC Updated Result:")
    results = await es.async_search("fish?", workspace_id=workspace_id, top_k=10)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async_dump_workspace
    dump_result = await es.async_dump_workspace(workspace_id=workspace_id)
    logger.info(f"Async dump result: {dump_result}")

    # Test async_load_workspace: delete workspace and reload from dump
    logger.info("ASYNC LOAD TEST - " + "=" * 20)
    await es.async_delete_workspace(workspace_id=workspace_id)
    logger.info(f"Workspace deleted, exist_workspace: {await es.async_exist_workspace(workspace_id)}")

    # Load workspace back
    load_result = await es.async_load_workspace(workspace_id)
    logger.info(f"Async load result: {load_result}")

    # Verify data is restored by searching
    results = await es.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"After async load, search returned {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Clean up
    await es.async_delete_workspace(workspace_id=workspace_id)
    await es.async_close()


if __name__ == "__main__":
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    asyncio.run(async_main())
