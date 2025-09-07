import asyncio
import fcntl
import json
import math
from functools import partial
from pathlib import Path
from typing import List, Iterable, Optional, Dict, Any

from loguru import logger
from pydantic import Field, model_validator
from tqdm import tqdm

from flowllm.context.service_context import C
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store.base_vector_store import BaseVectorStore


@C.register_vector_store("local")
class LocalVectorStore(BaseVectorStore):
    store_dir: str = Field(default="./local_vector_store")

    @model_validator(mode="after")
    def init_client(self):
        store_path = Path(self.store_dir)
        store_path.mkdir(parents=True, exist_ok=True)
        return self

    @staticmethod
    def _load_from_path(workspace_id: str, path: str | Path, callback_fn=None, **kwargs) -> Iterable[VectorNode]:
        workspace_path = Path(path) / f"{workspace_id}.jsonl"
        if not workspace_path.exists():
            logger.warning(f"workspace_path={workspace_path} is not exists!")
            return

        with workspace_path.open() as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                for line in tqdm(f, desc="load from path"):
                    if line.strip():
                        node_dict = json.loads(line.strip())
                        if callback_fn:
                            node = callback_fn(node_dict)
                        else:
                            node = VectorNode(**node_dict, **kwargs)
                        node.workspace_id = workspace_id
                        yield node

            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    @staticmethod
    def _dump_to_path(nodes: Iterable[VectorNode], workspace_id: str, path: str | Path = "", callback_fn=None,
                      ensure_ascii: bool = False, **kwargs):
        dump_path: Path = Path(path)
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_file = dump_path / f"{workspace_id}.jsonl"

        count = 0
        with dump_file.open("w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                for node in tqdm(nodes, desc="dump to path"):
                    node.workspace_id = workspace_id
                    if callback_fn:
                        node_dict = callback_fn(node)
                    else:
                        node_dict = node.model_dump()
                    assert isinstance(node_dict, dict)
                    f.write(json.dumps(node_dict, ensure_ascii=ensure_ascii, **kwargs))
                    f.write("\n")
                    count += 1

                return {"size": count}
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    @property
    def store_path(self) -> Path:
        return Path(self.store_dir)

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        workspace_path = self.store_path / f"{workspace_id}.jsonl"
        return workspace_path.exists()

    def delete_workspace(self, workspace_id: str, **kwargs):
        workspace_path = self.store_path / f"{workspace_id}.jsonl"
        if workspace_path.is_file():
            workspace_path.unlink()

    def create_workspace(self, workspace_id: str, **kwargs):
        self._dump_to_path(nodes=[], workspace_id=workspace_id, path=self.store_path, **kwargs)

    def iter_workspace_nodes(self, workspace_id: str, callback_fn=None, **kwargs):
        for node in self._load_from_path(path=self.store_path, workspace_id=workspace_id, callback_fn=callback_fn,
                                         **kwargs):
            yield node

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        if not self.exist_workspace(workspace_id=workspace_id, **kwargs):
            logger.warning(f"workspace_id={workspace_id} is not exist!")
            return {}

        return self._dump_to_path(
            nodes=self.iter_workspace_nodes(workspace_id=workspace_id, callback_fn=callback_fn, **kwargs),
                                  workspace_id=workspace_id,
                                  path=path,
                                  callback_fn=callback_fn,
                                  **kwargs)

    def load_workspace(self, workspace_id: str, path: str | Path = "", nodes: List[VectorNode] = None, callback_fn=None,
                       **kwargs):
        if self.exist_workspace(workspace_id, **kwargs):
            self.delete_workspace(workspace_id=workspace_id, **kwargs)
            logger.info(f"delete workspace_id={workspace_id}")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []
        if nodes:
            all_nodes.extend(nodes)
        for node in self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs):
            all_nodes.append(node)
        self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)
        return {"size": len(all_nodes)}

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        if not self.exist_workspace(workspace_id=src_workspace_id, **kwargs):
            logger.warning(f"src_workspace_id={src_workspace_id} is not exist!")
            return {}

        if not self.exist_workspace(dest_workspace_id, **kwargs):
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        nodes = []
        node_size = 0
        for node in self.iter_workspace_nodes(workspace_id=src_workspace_id, **kwargs):
            nodes.append(node)
            node_size += 1
            if len(nodes) >= self.batch_size:
                self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
                nodes.clear()

        if nodes:
            self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
        return {"size": node_size}

    @staticmethod
    def _matches_filters(node: VectorNode, filter_dict: dict = None) -> bool:
        """Check if a node matches all filters in filter_dict"""
        if not filter_dict:
            return True

        for key, filter_value in filter_dict.items():
            # Navigate nested keys (e.g., "metadata.node_type")
            value = node.metadata
            for key_part in key.split('.'):
                if isinstance(value, dict) and key_part in value:
                    value = value[key_part]
                else:
                    return False  # Key not found

            # Handle different filter types
            if isinstance(filter_value, dict):
                # Range filter: {"gte": 1, "lte": 10}
                if "gte" in filter_value and value < filter_value["gte"]:
                    return False
                if "lte" in filter_value and value > filter_value["lte"]:
                    return False
                if "gt" in filter_value and value <= filter_value["gt"]:
                    return False
                if "lt" in filter_value and value >= filter_value["lt"]:
                    return False
            else:
                # Term filter: direct value comparison
                if value != filter_value:
                    return False
        
        return True

    @staticmethod
    def calculate_similarity(query_vector: List[float], node_vector: List[float]):
        assert query_vector, f"query_vector is empty!"
        assert node_vector, f"node_vector is empty!"
        assert len(query_vector) == len(node_vector), \
            f"query_vector.size={len(query_vector)} node_vector.size={len(node_vector)}"

        dot_product = sum(x * y for x, y in zip(query_vector, node_vector))
        norm_v1 = math.sqrt(sum(x ** 2 for x in query_vector))
        norm_v2 = math.sqrt(sum(y ** 2 for y in node_vector))
        return dot_product / (norm_v1 * norm_v2)

    def search(self, query: str, workspace_id: str, top_k: int = 1, filter_dict: Optional[Dict[str, Any]] = None,
               **kwargs) -> List[VectorNode]:
        query_vector = self.embedding_model.get_embeddings(query)
        nodes: List[VectorNode] = []
        for node in self._load_from_path(path=self.store_path, workspace_id=workspace_id, **kwargs):
            # Apply filters
            if self._matches_filters(node, filter_dict):
                node.metadata["score"] = self.calculate_similarity(query_vector, node.vector)
                nodes.append(node)

        nodes = sorted(nodes, key=lambda x: x.metadata["score"], reverse=True)
        return nodes[:top_k]

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        all_node_dict = {}
        nodes: List[VectorNode] = self.embedding_model.get_node_embeddings(nodes)
        exist_nodes: List[VectorNode] = list(self._load_from_path(path=self.store_path, workspace_id=workspace_id))
        for node in exist_nodes:
            all_node_dict[node.unique_id] = node

        update_cnt = 0
        for node in nodes:
            if node.unique_id in all_node_dict:
                update_cnt += 1

            all_node_dict[node.unique_id] = node

        self._dump_to_path(nodes=list(all_node_dict.values()),
                           workspace_id=workspace_id,
                           path=self.store_path,
                           **kwargs)

        logger.info(f"update workspace_id={workspace_id} nodes.size={len(nodes)} all.size={len(all_node_dict)} "
                    f"update_cnt={update_cnt}")

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} is not exists!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        all_nodes: List[VectorNode] = list(self._load_from_path(path=self.store_path, workspace_id=workspace_id))
        before_size = len(all_nodes)
        all_nodes = [n for n in all_nodes if n.unique_id not in node_ids]
        after_size = len(all_nodes)

        self._dump_to_path(nodes=all_nodes, workspace_id=workspace_id, path=self.store_path, **kwargs)
        logger.info(f"delete workspace_id={workspace_id} before_size={before_size} after_size={after_size}")

    # Override async methods for better performance with file I/O
    async def async_search(self, query: str, workspace_id: str, top_k: int = 1,
                           filter_dict: Optional[Dict[str, Any]] = None, **kwargs) -> List[VectorNode]:
        """Async version of search using embedding model async capabilities"""
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # Load nodes asynchronously
        loop = asyncio.get_event_loop()
        nodes_iter = await loop.run_in_executor(
            C.thread_pool,
            partial(self._load_from_path, path=self.store_path, workspace_id=workspace_id, **kwargs)
        )

        nodes: List[VectorNode] = []
        for node in nodes_iter:
            # Apply filters
            if self._matches_filters(node, filter_dict):
                node.metadata["score"] = self.calculate_similarity(query_vector, node.vector)
                nodes.append(node)

        nodes = sorted(nodes, key=lambda x: x.metadata["score"], reverse=True)
        return nodes[:top_k]

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert using embedding model async capabilities"""
        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        # Use async embedding
        nodes = await self.embedding_model.get_node_embeddings_async(nodes)

        # Load existing nodes asynchronously
        loop = asyncio.get_event_loop()
        exist_nodes_iter = await loop.run_in_executor(
            C.thread_pool,
            partial(self._load_from_path, path=self.store_path, workspace_id=workspace_id)
        )

        all_node_dict = {}
        exist_nodes: List[VectorNode] = list(exist_nodes_iter)
        for node in exist_nodes:
            all_node_dict[node.unique_id] = node

        update_cnt = 0
        for node in nodes:
            if node.unique_id in all_node_dict:
                update_cnt += 1
            all_node_dict[node.unique_id] = node

        # Dump to path asynchronously
        await loop.run_in_executor(
            C.thread_pool,
            partial(self._dump_to_path, nodes=list(all_node_dict.values()),
                    workspace_id=workspace_id, path=self.store_path, **kwargs)
        )

        logger.info(f"update workspace_id={workspace_id} nodes.size={len(nodes)} all.size={len(all_node_dict)} "
                    f"update_cnt={update_cnt}")


def main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "rag_nodes_index"
    client = LocalVectorStore(embedding_model=embedding_model)
    client.delete_workspace(workspace_id)
    client.create_workspace(workspace_id)

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

    client.insert(sample_nodes, workspace_id)

    logger.info("=" * 20)
    results = client.search("What is AI?", workspace_id=workspace_id, top_k=5)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test filter_dict
    logger.info("=" * 20 + " FILTER TEST " + "=" * 20)
    filter_dict = {"node_type": "n1"}
    results = client.search("What is AI?", workspace_id=workspace_id, top_k=5, filter_dict=filter_dict)
    logger.info(f"Filtered results (node_type=n1): {len(results)} results")
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)
    client.dump_workspace(workspace_id)

    client.delete_workspace(workspace_id)


async def async_main():
    from flowllm.utils.common_utils import load_env
    from flowllm.embedding_model import OpenAICompatibleEmbeddingModel

    load_env()

    embedding_model = OpenAICompatibleEmbeddingModel(dimensions=64, model_name="text-embedding-v4")
    workspace_id = "async_rag_nodes_index"
    client = LocalVectorStore(embedding_model=embedding_model, store_dir="./async_file_vector_store")

    # Clean up and create workspace
    if await client.async_exist_workspace(workspace_id):
        await client.async_delete_workspace(workspace_id)
    await client.async_create_workspace(workspace_id)

    sample_nodes = [
        VectorNode(
            unique_id="async_local_node1",
            workspace_id=workspace_id,
            content="Artificial intelligence is a technology that simulates human intelligence.",
            metadata={
                "node_type": "n1",
            }
        ),
        VectorNode(
            unique_id="async_local_node2",
            workspace_id=workspace_id,
            content="AI is the future of mankind.",
            metadata={
                "node_type": "n1",
            }
        ),
        VectorNode(
            unique_id="async_local_node3",
            workspace_id=workspace_id,
            content="I want to eat fish!",
            metadata={
                "node_type": "n2",
            }
        ),
        VectorNode(
            unique_id="async_local_node4",
            workspace_id=workspace_id,
            content="The bigger the storm, the more expensive the fish.",
            metadata={
                "node_type": "n1",
            }
        ),
    ]

    # Test async insert
    await client.async_insert(sample_nodes, workspace_id)

    logger.info("ASYNC TEST - " + "=" * 20)
    # Test async search
    results = await client.async_search("What is AI?", workspace_id=workspace_id, top_k=5)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Test async update (delete + insert)
    node2_update = VectorNode(
        unique_id="async_local_node2",
        workspace_id=workspace_id,
        content="AI is the future of humanity and technology.",
        metadata={
            "node_type": "n1",
            "updated": True
        }
    )
    await client.async_delete(node2_update.unique_id, workspace_id=workspace_id)
    await client.async_insert(node2_update, workspace_id=workspace_id)

    logger.info("ASYNC Updated Result:")
    results = await client.async_search("fish?", workspace_id=workspace_id, top_k=10)
    for r in results:
        logger.info(r.model_dump(exclude={"vector"}))
    logger.info("=" * 20)

    # Clean up
    await client.async_dump_workspace(workspace_id)
    await client.async_delete_workspace(workspace_id)


if __name__ == "__main__":
    main()

    # Run async test
    logger.info("\n" + "=" * 50 + " ASYNC TESTS " + "=" * 50)
    asyncio.run(async_main())
