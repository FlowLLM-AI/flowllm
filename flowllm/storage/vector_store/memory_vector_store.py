import asyncio
from functools import partial
from pathlib import Path
from typing import List, Dict, Optional, Any

from loguru import logger
from pydantic import Field

from flowllm.context.service_context import C
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store.local_vector_store import LocalVectorStore


@C.register_vector_store("memory")
class MemoryVectorStore(LocalVectorStore):
    """
    In-memory vector store that keeps all data in memory for fast access.
    Only saves to disk when dump_workspace is called.
    Can load previously saved data via load_workspace.
    """
    store_dir: str = Field(default="./memory_vector_store")
    
    def __init__(self, **data):
        super().__init__(**data)
        self._memory_store: Dict[str, Dict[str, VectorNode]] = {}

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        return workspace_id in self._memory_store

    def delete_workspace(self, workspace_id: str, **kwargs):
        if workspace_id in self._memory_store:
            del self._memory_store[workspace_id]
            logger.info(f"Deleted workspace_id={workspace_id} from memory")

    def create_workspace(self, workspace_id: str, **kwargs):
        if workspace_id not in self._memory_store:
            self._memory_store[workspace_id] = {}
            logger.info(f"Created workspace_id={workspace_id} in memory")

    def iter_workspace_nodes(self, workspace_id: str, callback_fn=None, **kwargs):
        if workspace_id in self._memory_store:
            for node in self._memory_store[workspace_id].values():
                if callback_fn:
                    yield callback_fn(node)
                else:
                    yield node

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return {}

        dump_path = Path(path) if path else self.store_path
        nodes = list(self._memory_store[workspace_id].values())

        return self._dump_to_path(nodes=nodes,
                                  workspace_id=workspace_id,
                                  path=dump_path,
                                  callback_fn=callback_fn,
                                  **kwargs)

    def load_workspace(self, workspace_id: str, path: str | Path = "", nodes: Optional[List[VectorNode]] = None,
                       callback_fn=None, **kwargs):
        if workspace_id in self._memory_store:
            del self._memory_store[workspace_id]
            logger.info(f"Cleared existing workspace_id={workspace_id} from memory")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        if path:
            for node in self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs):
                all_nodes.append(node)

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)
        
        logger.info(f"Loaded workspace_id={workspace_id} with {len(all_nodes)} nodes into memory")
        return {"size": len(all_nodes)}

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        if src_workspace_id not in self._memory_store:
            logger.warning(f"src_workspace_id={src_workspace_id} not found in memory!")
            return {}

        if dest_workspace_id not in self._memory_store:
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = list(self._memory_store[src_workspace_id].values())
        node_size = len(src_nodes)
        
        for i in range(0, node_size, self.batch_size):
            batch_nodes = src_nodes[i:i + self.batch_size]
            new_nodes = []
            for node in batch_nodes:
                new_node = VectorNode(**node.model_dump())
                new_node.workspace_id = dest_workspace_id
                new_nodes.append(new_node)
            
            self.insert(nodes=new_nodes, workspace_id=dest_workspace_id, **kwargs)

        logger.info(f"Copied {node_size} nodes from {src_workspace_id} to {dest_workspace_id}")
        return {"size": node_size}

    def search(self, query: str, workspace_id: str, top_k: int = 1, filter_dict: Optional[Dict[str, Any]] = None,
               **kwargs) -> List[VectorNode]:
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return []

        query_vector = self.embedding_model.get_embeddings(query)
        nodes: List[VectorNode] = []
        
        for node in self._memory_store[workspace_id].values():
            if node.vector and self._matches_filters(node, filter_dict):
                score = self.calculate_similarity(query_vector, node.vector)
                result_node = VectorNode(**node.model_dump())
                result_node.metadata["score"] = score
                nodes.append(result_node)

        nodes = sorted(nodes, key=lambda x: x.metadata["score"], reverse=True)
        return nodes[:top_k]

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        if workspace_id not in self._memory_store:
            self.create_workspace(workspace_id=workspace_id, **kwargs)

        nodes: List[VectorNode] = self.embedding_model.get_node_embeddings(nodes)
        
        update_cnt = 0
        for node in nodes:
            if node.unique_id in self._memory_store[workspace_id]:
                update_cnt += 1
            
            node.workspace_id = workspace_id
            self._memory_store[workspace_id][node.unique_id] = node

        total_nodes = len(self._memory_store[workspace_id])
        logger.info(f"Inserted into workspace_id={workspace_id} nodes.size={len(nodes)} "
                   f"total.size={total_nodes} update_cnt={update_cnt}")

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        before_size = len(self._memory_store[workspace_id])
        deleted_cnt = 0
        
        for node_id in node_ids:
            if node_id in self._memory_store[workspace_id]:
                del self._memory_store[workspace_id][node_id]
                deleted_cnt += 1

        after_size = len(self._memory_store[workspace_id])
        logger.info(f"Deleted from workspace_id={workspace_id} before_size={before_size} "
                   f"after_size={after_size} deleted_cnt={deleted_cnt}")

    async def async_search(self, query: str, workspace_id: str, top_k: int = 1,
                           filter_dict: Optional[Dict[str, Any]] = None, **kwargs) -> List[VectorNode]:
        """Async version of search using embedding model async capabilities"""
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return []

        query_vector = await self.embedding_model.get_embeddings_async(query)
        nodes: List[VectorNode] = []
        
        for node in self._memory_store[workspace_id].values():
            # Apply filters and only consider nodes with vectors
            if node.vector and self._matches_filters(node, filter_dict):
                score = self.calculate_similarity(query_vector, node.vector)
                # Create a copy to avoid modifying original
                result_node = VectorNode(**node.model_dump())
                result_node.metadata["score"] = score
                nodes.append(result_node)

        nodes = sorted(nodes, key=lambda x: x.metadata["score"], reverse=True)
        return nodes[:top_k]

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert using embedding model async capabilities"""
        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        # Ensure workspace exists
        if workspace_id not in self._memory_store:
            self.create_workspace(workspace_id=workspace_id, **kwargs)

        # Use async embedding
        nodes = await self.embedding_model.get_node_embeddings_async(nodes)
        
        update_cnt = 0
        for node in nodes:
            if node.unique_id in self._memory_store[workspace_id]:
                update_cnt += 1
            
            node.workspace_id = workspace_id
            self._memory_store[workspace_id][node.unique_id] = node

        total_nodes = len(self._memory_store[workspace_id])
        logger.info(f"Async inserted into workspace_id={workspace_id} nodes.size={len(nodes)} "
                   f"total.size={total_nodes} update_cnt={update_cnt}")

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Async version of dump_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(self.dump_workspace, workspace_id, path, callback_fn, **kwargs)
        )

    async def async_load_workspace(self, workspace_id: str, path: str | Path = "", nodes: List[VectorNode] = None,
                                   callback_fn=None, **kwargs):
        """Async version of load_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(self.load_workspace, workspace_id, path, nodes, callback_fn, **kwargs)
        )

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace"""
        return self.exist_workspace(workspace_id, **kwargs)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Async version of delete_workspace"""
        return self.delete_workspace(workspace_id, **kwargs)

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Async version of create_workspace"""
        return self.create_workspace(workspace_id, **kwargs)

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete"""
        return self.delete(node_ids, workspace_id, **kwargs)

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Async version of copy_workspace"""
        return self.copy_workspace(src_workspace_id, dest_workspace_id, **kwargs)


def main():
    """Test the MemoryVectorStore with synchronous operations"""
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

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
                "category": "AI"
            }
        ),
        VectorNode(
            unique_id="memory_node2",
            workspace_id=workspace_id,
            content="Machine learning is a subset of artificial intelligence.",
            metadata={
                "node_type": "tech",
                "category": "ML"
            }
        ),
        VectorNode(
            unique_id="memory_node3",
            workspace_id=workspace_id,
            content="I love eating delicious seafood, especially fresh fish.",
            metadata={
                "node_type": "food",
                "category": "preference"
            }
        ),
        VectorNode(
            unique_id="memory_node4",
            workspace_id=workspace_id,
            content="Deep learning uses neural networks with multiple layers.",
            metadata={
                "node_type": "tech",
                "category": "DL"
            }
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
    results = client.search("What is artificial intelligence?", workspace_id=workspace_id, top_k=5,
                            filter_dict=filter_dict)
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
            "updated": True
        }
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
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

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
                "category": "quantum"
            }
        ),
        VectorNode(
            unique_id="async_memory_node2",
            workspace_id=workspace_id,
            content="Blockchain technology enables decentralized applications.",
            metadata={
                "node_type": "tech",
                "category": "blockchain"
            }
        ),
        VectorNode(
            unique_id="async_memory_node3",
            workspace_id=workspace_id,
            content="Cloud computing provides scalable infrastructure solutions.",
            metadata={
                "node_type": "tech",
                "category": "cloud"
            }
        ),
        VectorNode(
            unique_id="async_memory_node4",
            workspace_id=workspace_id,
            content="Pizza is my favorite Italian food with cheese and tomatoes.",
            metadata={
                "node_type": "food",
                "category": "italian"
            }
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
            "version": "2.0"
        }
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
