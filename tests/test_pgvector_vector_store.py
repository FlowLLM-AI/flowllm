"""Test script for PgVectorStore.

This script provides test functions for both synchronous and asynchronous
vector store operations. It can be run directly with: python test_pgvector_vector_store.py

Requires proper environment variables:
- FLOW_EMBEDDING_API_KEY: API key for authentication
- FLOW_EMBEDDING_BASE_URL: Base URL for the API endpoint
- FLOW_PGVECTOR_CONNECTION_STRING: PostgreSQL connection string (optional, defaults to postgresql://localhost/postgres)
- FLOW_PGVECTOR_ASYNC_CONNECTION_STRING: Async PostgreSQL connection string (optional)

Also requires:
- PostgreSQL database with pgvector extension installed
- pgvector Python package: pip install pgvector[sqlalchemy]
- PostgreSQL driver: pip install psycopg2-binary (for sync) or asyncpg (for async)
"""

import asyncio

from loguru import logger

from flowllm.core.embedding_model.openai_compatible_embedding_model import (
    OpenAICompatibleEmbeddingModel,
)
from flowllm.core.schema.vector_node import VectorNode
from flowllm.core.utils import load_env
from flowllm.core.vector_store.pgvector_vector_store import PgVectorStore

load_env()


def main():
    """
    Test the PgVectorStore with synchronous operations.

    This function demonstrates basic operations including create, insert, search,
    filtering, update (delete + insert), dump_workspace, load_workspace, and workspace management.
    """
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "rag_nodes_index"
    connection_string = "postgresql://localhost/postgres"
    
    pg = PgVectorStore(connection_string=connection_string, embedding_model=embedding_model)
    
    # Clean up and create workspace
    if pg.exist_workspace(workspace_id=workspace_id):
        pg.delete_workspace(workspace_id=workspace_id)
    pg.create_workspace(workspace_id=workspace_id)

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

    pg.insert(sample_nodes, workspace_id=workspace_id, refresh=True)

    logger.info("=" * 20 + " FILTER TEST " + "=" * 20)
    filter_dict = {"node_type": "n1"}
    results = pg.search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
    logger.info(f"Filtered results (node_type=n1): {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    logger.info("=" * 20 + " UNFILTERED TEST " + "=" * 20)
    results = pg.search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"Unfiltered results: {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test dump_workspace
    dump_result = pg.dump_workspace(workspace_id=workspace_id)
    logger.info(f"Dump result: {dump_result}")

    # Test load_workspace: delete workspace and reload from dump
    logger.info("=" * 20 + " LOAD TEST " + "=" * 20)
    pg.delete_workspace(workspace_id=workspace_id)
    logger.info(f"Workspace deleted, exist_workspace: {pg.exist_workspace(workspace_id)}")

    # Load workspace back
    load_result = pg.load_workspace(workspace_id)
    logger.info(f"Load result: {load_result}")

    # Verify data is restored by searching
    results = pg.search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"After load, search returned {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test list_workspace
    logger.info("=" * 20 + " LIST WORKSPACE TEST " + "=" * 20)
    workspaces = pg.list_workspace()
    logger.info(f"List of workspaces: {workspaces}")
    logger.info("=" * 20)

    # Test iter_workspace_nodes
    logger.info("=" * 20 + " ITER WORKSPACE NODES TEST " + "=" * 20)
    node_count = 0
    for node in pg.iter_workspace_nodes(workspace_id=workspace_id):
        node_count += 1
        logger.info(f"Node {node_count}: {node.unique_id} - {node.content[:50]}...")
    logger.info(f"Total nodes iterated: {node_count}")
    logger.info("=" * 20)

    pg.delete_workspace(workspace_id=workspace_id)
    pg.close()


async def async_main():
    """
    Test the PgVectorStore with asynchronous operations.

    This function demonstrates async operations including async_create_workspace,
    async_insert, async_search, async_delete, async_dump_workspace, and
    async_load_workspace for better performance in async applications.
    """
    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "async_rag_nodes_index"
    connection_string = "postgresql://localhost/postgres"
    async_connection_string = "postgresql+asyncpg://localhost/postgres"

    # Use async connection
    pg = PgVectorStore(
        connection_string=connection_string,
        async_connection_string=async_connection_string,
        embedding_model=embedding_model,
    )
    
    # Clean up and create workspace
    if await pg.async_exist_workspace(workspace_id=workspace_id):
        await pg.async_delete_workspace(workspace_id=workspace_id)
    await pg.async_create_workspace(workspace_id=workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="async_pg_node1",
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            unique_id="async_pg_node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
            },
        ),
        VectorNode(
            unique_id="async_pg_node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
            },
        ),
        VectorNode(
            unique_id="async_pg_node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
            },
        ),
    ]

    # Test async insert
    await pg.async_insert(sample_nodes, workspace_id=workspace_id, refresh=True)

    logger.info("ASYNC TEST - " + "=" * 20)
    # Test async search with filter
    filter_dict = {"node_type": "n1"}
    results = await pg.async_search("What is AI?", top_k=5, workspace_id=workspace_id, filter_dict=filter_dict)
    logger.info(f"Filtered results (node_type=n1): {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async search without filter
    logger.info("ASYNC TEST WITHOUT FILTER - " + "=" * 20)
    results = await pg.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"Unfiltered results: {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async update (delete + insert)
    node2_update = VectorNode(
        unique_id="async_pg_node2",
        workspace_id=workspace_id,
        content="AI is the future of humanity and technology.",
        metadata={
            "node_type": "n1",
            "updated": True,
        },
    )
    await pg.async_delete(node2_update.unique_id, workspace_id=workspace_id, refresh=True)
    await pg.async_insert(node2_update, workspace_id=workspace_id, refresh=True)

    logger.info("ASYNC Updated Result:")
    results = await pg.async_search("fish?", workspace_id=workspace_id, top_k=10)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async_dump_workspace
    dump_result = await pg.async_dump_workspace(workspace_id=workspace_id)
    logger.info(f"Async dump result: {dump_result}")

    # Test async_load_workspace: delete workspace and reload from dump
    logger.info("ASYNC LOAD TEST - " + "=" * 20)
    await pg.async_delete_workspace(workspace_id=workspace_id)
    logger.info(f"Workspace deleted, exist_workspace: {await pg.async_exist_workspace(workspace_id)}")

    # Load workspace back
    load_result = await pg.async_load_workspace(workspace_id)
    logger.info(f"Async load result: {load_result}")

    # Verify data is restored by searching
    results = await pg.async_search("What is AI?", top_k=5, workspace_id=workspace_id)
    logger.info(f"After async load, search returned {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Clean up
    await pg.async_delete_workspace(workspace_id=workspace_id)
    await pg.async_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Sync test failed: {e}")
        import traceback
        traceback.print_exc()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    try:
        asyncio.run(async_main())
    except Exception as e:
        logger.error(f"Async test failed: {e}")
        import traceback
        traceback.print_exc()

