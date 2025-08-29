from abc import ABC
from pathlib import Path
from typing import List, Iterable

from pydantic import BaseModel, Field

from flowllm.embedding_model.base_embedding_model import BaseEmbeddingModel
from flowllm.schema.vector_node import VectorNode


class BaseVectorStore(BaseModel, ABC):
    embedding_model: BaseEmbeddingModel | None = Field(default=None)
    batch_size: int = Field(default=1024)

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        raise NotImplementedError

    def delete_workspace(self, workspace_id: str, **kwargs):
        raise NotImplementedError

    def create_workspace(self, workspace_id: str, **kwargs):
        raise NotImplementedError

    def _iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        raise NotImplementedError

    def iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        return self._iter_workspace_nodes(workspace_id, **kwargs)

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        raise NotImplementedError

    def load_workspace(self, workspace_id: str, path: str | Path = "", nodes: List[VectorNode] = None, callback_fn=None,
                       **kwargs):
        raise NotImplementedError

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        raise NotImplementedError

    def search(self, query: str, workspace_id: str, top_k: int = 1, **kwargs) -> List[VectorNode]:
        raise NotImplementedError

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        raise NotImplementedError

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        raise NotImplementedError
