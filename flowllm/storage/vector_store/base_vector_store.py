import asyncio
from abc import ABC
from functools import partial
from pathlib import Path
from typing import List, Iterable

from pydantic import BaseModel, Field

from flowllm.context.service_context import C
from flowllm.embedding_model.base_embedding_model import BaseEmbeddingModel
from flowllm.schema.vector_node import VectorNode


class BaseVectorStore(BaseModel, ABC):
    embedding_model: BaseEmbeddingModel | None = Field(default=None)
    batch_size: int = Field(default=1024)
    retrieve_filters: List[dict] = []

    def add_term_filter(self, key: str, value):
        raise NotImplementedError

    def add_dict_filter(self, **kwargs):
        for k, v in kwargs.items():
            self.add_term_filter(k, v)
        return self

    def add_range_filter(self, key: str, gte=None, lte=None):
        raise NotImplementedError

    def clear_filter(self):
        self.retrieve_filters.clear()
        return self

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

    def close(self):
        ...

    # Async versions of all methods
    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.exist_workspace, workspace_id, **kwargs))

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Async version of delete_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.delete_workspace, workspace_id, **kwargs))

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Async version of create_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.create_workspace, workspace_id, **kwargs))

    async def async_iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        """Async version of iter_workspace_nodes"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.iter_workspace_nodes, workspace_id, **kwargs))

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """Async version of dump_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool,
                                          partial(self.dump_workspace, workspace_id, path, callback_fn, **kwargs))

    async def async_load_workspace(self, workspace_id: str, path: str | Path = "", nodes: List[VectorNode] = None,
                                   callback_fn=None, **kwargs):
        """Async version of load_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool,
                                          partial(self.load_workspace, workspace_id, path, nodes, callback_fn,
                                                  **kwargs))

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Async version of copy_workspace"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool,
                                          partial(self.copy_workspace, src_workspace_id, dest_workspace_id, **kwargs))

    async def async_search(self, query: str, workspace_id: str, top_k: int = 1, **kwargs) -> List[VectorNode]:
        """Async version of search"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.search, query, workspace_id, top_k, **kwargs))

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Async version of insert"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.insert, nodes, workspace_id, **kwargs))

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Async version of delete"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.delete, node_ids, workspace_id, **kwargs))

    async def aclose(self):
        """Async version of close"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, self.close)
