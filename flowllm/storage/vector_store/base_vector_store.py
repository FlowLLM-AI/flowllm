import asyncio
from abc import ABC, abstractmethod
from functools import partial
from pathlib import Path
from typing import List, Iterable, Dict, Any, Optional

from pydantic import BaseModel, Field

from flowllm.context.service_context import C
from flowllm.embedding_model.base_embedding_model import BaseEmbeddingModel
from flowllm.schema.vector_node import VectorNode


class BaseVectorStore(BaseModel, ABC):
    embedding_model: BaseEmbeddingModel | None = Field(default=None)
    batch_size: int = Field(default=1024)

    @abstractmethod
    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a workspace exists in the vector store."""
        raise NotImplementedError

    @abstractmethod
    def delete_workspace(self, workspace_id: str, **kwargs) -> None:
        """Delete a workspace from the vector store."""
        raise NotImplementedError

    @abstractmethod
    def create_workspace(self, workspace_id: str, **kwargs) -> None:
        """Create a new workspace in the vector store."""
        raise NotImplementedError

    @abstractmethod
    def iter_workspace_nodes(self, workspace_id: str, callback_fn=None, **kwargs) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace."""
        raise NotImplementedError

    @abstractmethod
    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs) -> None:
        """Dump workspace data to a file or path."""
        raise NotImplementedError

    @abstractmethod
    def load_workspace(self, workspace_id: str, path: str | Path = "", nodes: Optional[List[VectorNode]] = None,
                       callback_fn=None, **kwargs) -> None:
        """Load workspace data from a file or path, or from provided nodes."""
        raise NotImplementedError

    @abstractmethod
    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs) -> None:
        """Copy one workspace to another."""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, workspace_id: str, top_k: int = 1, filter_dict: Optional[Dict[str, Any]] = None,
               **kwargs) -> List[VectorNode]:
        """Search for similar vectors in the workspace."""
        raise NotImplementedError

    @abstractmethod
    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs) -> None:
        """Insert nodes into the workspace."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs) -> None:
        """Delete nodes from the workspace by their IDs."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the vector store and clean up resources. Default implementation does nothing."""
        pass

    """
    Async versions of all methods
    """

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Async version of exist_workspace."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.exist_workspace, workspace_id, **kwargs))

    async def async_delete_workspace(self, workspace_id: str, **kwargs) -> None:
        """Async version of delete_workspace."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.delete_workspace, workspace_id, **kwargs))

    async def async_create_workspace(self, workspace_id: str, **kwargs) -> None:
        """Async version of create_workspace."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.create_workspace, workspace_id, **kwargs))

    async def async_iter_workspace_nodes(self, workspace_id: str, callback_fn=None, **kwargs) -> Iterable[VectorNode]:
        """Async version of iter_workspace_nodes. Returns an iterable, not an async iterator."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.iter_workspace_nodes, workspace_id,
                                                                 callback_fn, **kwargs))

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.dump_workspace, workspace_id, path,
                                                                 callback_fn, **kwargs))

    async def async_load_workspace(self, workspace_id: str, path: str | Path = "", nodes: List[VectorNode] = None,
                                   callback_fn=None, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.load_workspace, workspace_id, path, nodes,
                                                                 callback_fn, **kwargs))

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.copy_workspace, src_workspace_id,
                                                                 dest_workspace_id, **kwargs))

    async def async_search(self, query: str, workspace_id: str, top_k: int = 1, filter_dict: dict = None,
                           **kwargs) -> List[VectorNode]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.search, query, workspace_id, top_k,
                                                                 filter_dict, **kwargs))

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.insert, nodes, workspace_id, **kwargs))

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, partial(self.delete, node_ids, workspace_id, **kwargs))

    async def async_close(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(C.thread_pool, self.close)
