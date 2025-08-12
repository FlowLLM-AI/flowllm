import fcntl
import json
import math
from pathlib import Path
from typing import List, Iterable

from loguru import logger
from pydantic import Field, model_validator
from tqdm import tqdm

from flowllm.context.registry_context import register_vector_store
from flowllm.schema.vector_node import VectorNode
from flowllm.storage.vector_store.base_vector_store import BaseVectorStore


@register_vector_store("local")
class LocalVectorStore(BaseVectorStore):
    store_dir: str = Field(default="./file_vector_store")

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

    def _iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        for i, node in enumerate(self._load_from_path(path=self.store_path, workspace_id=workspace_id, **kwargs)):
            yield node

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        if not self.exist_workspace(workspace_id=workspace_id, **kwargs):
            logger.warning(f"workspace_id={workspace_id} is not exist!")
            return {}

        return self._dump_to_path(nodes=self._iter_workspace_nodes(workspace_id=workspace_id, **kwargs),
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
        for node in self._iter_workspace_nodes(workspace_id=src_workspace_id, **kwargs):
            nodes.append(node)
            node_size += 1
            if len(nodes) >= self.batch_size:
                self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
                nodes.clear()

        if nodes:
            self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
        return {"size": node_size}

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

    def search(self, query: str, workspace_id: str, top_k: int = 1, **kwargs) -> List[VectorNode]:
        query_vector = self.embedding_model.get_embeddings(query)
        nodes: List[VectorNode] = []
        for node in self._load_from_path(path=self.store_path, workspace_id=workspace_id, **kwargs):
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
    client.dump_workspace(workspace_id)

    client.delete_workspace(workspace_id)


if __name__ == "__main__":
    main()
