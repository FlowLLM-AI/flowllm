"""
In-memory vector store implementation.

This module provides an in-memory vector store that keeps all data in memory
for fast access. It inherits from LocalVectorStore and can persist data to disk
when needed via dump_workspace and load_workspace methods.
"""

import asyncio
from functools import partial
from pathlib import Path
from typing import List, Dict, Optional, Any

from loguru import logger

from .local_vector_store import LocalVectorStore
from ..context import C
from ..schema import VectorNode


@C.register_vector_store("memory")
class MemoryVectorStore(LocalVectorStore):
    """
    In-memory vector store that keeps all data in memory for fast access.
    Only saves to disk when dump_workspace is called.
    Can load previously saved data via load_workspace.
    """

    def __init__(self, store_dir: str = "./memory_vector_store", **kwargs):
        """
        Initialize the memory vector store.

        Args:
            store_dir: Directory path where workspace files are stored.
            **kwargs: Keyword arguments passed to the parent LocalVectorStore class.
        """
        super().__init__(store_dir=store_dir, **kwargs)
        self._memory_store: Dict[str, Dict[str, VectorNode]] = {}
        logger.info(f"MemoryVectorStore initialized with store_dir={self.store_dir}")

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """
        Check if a workspace exists in memory.

        Args:
            workspace_id: Identifier of the workspace to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the workspace exists in memory, False otherwise.
        """
        return workspace_id in self._memory_store

    def delete_workspace(self, workspace_id: str, **kwargs):
        """
        Delete a workspace and all its nodes from memory.

        Args:
            workspace_id: Identifier of the workspace to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        if workspace_id in self._memory_store:
            del self._memory_store[workspace_id]
            logger.info(f"Deleted workspace_id={workspace_id} from memory")

    def create_workspace(self, workspace_id: str, **kwargs):
        """
        Create a new empty workspace in memory.

        Args:
            workspace_id: Identifier for the new workspace.
            **kwargs: Additional keyword arguments (unused).
        """
        if workspace_id not in self._memory_store:
            self._memory_store[workspace_id] = {}
            logger.info(f"Created workspace_id={workspace_id} in memory")

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces in memory.

        Returns:
            List[str]: Workspace identifiers currently present in memory.
        """
        return list(self._memory_store.keys())

    def iter_workspace_nodes(self, workspace_id: str, **kwargs):
        """
        Iterate over all nodes in a workspace.

        Args:
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments (unused).

        Yields:
            VectorNode: Nodes from the workspace, one at a time.
        """
        if workspace_id in self._memory_store:
            yield from self._memory_store[workspace_id].values()

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """
        Export a workspace from memory to disk at the specified path.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
                  If empty, uses the current store_path.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist in memory.
        """
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return {}

        dump_path = Path(path) if path else self.store_path
        nodes = list(self._memory_store[workspace_id].values())

        return self._dump_to_path(
            nodes=nodes,
            workspace_id=workspace_id,
            path=dump_path,
            callback_fn=callback_fn,
            **kwargs,
        )

    def load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: Optional[List[VectorNode]] = None,
        callback_fn=None,
        **kwargs,
    ):
        """
        Load a workspace into memory from disk, optionally merging with provided nodes.

        This method replaces any existing workspace with the same ID in memory,
        then loads nodes from the specified path and/or the provided nodes list.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
                  If empty, only loads from nodes parameter.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        if workspace_id in self._memory_store:
            del self._memory_store[workspace_id]
            logger.info(f"Cleared existing workspace_id={workspace_id} from memory")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        for node in self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs):
            all_nodes.append(node)

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)

        logger.info(f"Loaded workspace_id={workspace_id} with {len(all_nodes)} nodes into memory")
        return {"size": len(all_nodes)}

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """
        Copy all nodes from one workspace to another in memory.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist in memory.
        """
        if src_workspace_id not in self._memory_store:
            logger.warning(f"src_workspace_id={src_workspace_id} not found in memory!")
            return {}

        if dest_workspace_id not in self._memory_store:
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = list(self._memory_store[src_workspace_id].values())
        node_size = len(src_nodes)

        new_nodes = []
        for node in src_nodes:
            new_node = VectorNode(**node.model_dump())
            new_node.workspace_id = dest_workspace_id
            new_nodes.append(new_node)

        self.insert(nodes=new_nodes, workspace_id=dest_workspace_id, **kwargs)

        logger.info(f"Copied {node_size} nodes from {src_workspace_id} to {dest_workspace_id}")
        return {"size": node_size}

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """
        Search for similar nodes using vector similarity in memory.

        Args:
            query: Text query to search for.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of top_k most similar nodes, sorted by similarity score
                             (highest first). Each node has a "score" key added to its metadata.
                             Returns empty list if workspace doesn't exist in memory.
        """
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
        """
        Insert or update nodes in a workspace in memory.

        If a node with the same unique_id already exists, it will be updated.
        New nodes will be added. All nodes are embedded before insertion.
        Workspace is created automatically if it doesn't exist.

        Args:
            nodes: Single VectorNode or list of VectorNode instances to insert/update.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
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
        logger.info(
            f"Inserted into workspace_id={workspace_id} nodes.size={len(nodes)} "
            f"total.size={total_nodes} update_cnt={update_cnt}",
        )

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """
        Delete nodes from a workspace by their unique IDs in memory.

        Args:
            node_ids: Single unique_id string or list of unique_id strings to delete.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
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
        logger.info(
            f"Deleted from workspace_id={workspace_id} before_size={before_size} "
            f"after_size={after_size} deleted_cnt={deleted_cnt}",
        )

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """
        Async version of search using embedding model async capabilities.

        This method performs the same search operation as search(), but uses
        async embedding generation for better performance in async contexts.

        Args:
            query: Text query to search for.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of top_k most similar nodes, sorted by similarity score
                             (highest first). Each node has a "score" key added to its metadata.
                             Returns empty list if workspace doesn't exist in memory.
        """
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
        """
        Async version of insert using embedding model async capabilities.

        This method performs the same insert operation as insert(), but uses
        async embedding generation for better performance in async contexts.

        Args:
            nodes: Single VectorNode or list of VectorNode instances to insert/update.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
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
        logger.info(
            f"Async inserted into workspace_id={workspace_id} nodes.size={len(nodes)} "
            f"total.size={total_nodes} update_cnt={update_cnt}",
        )

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """
        Async version of dump_workspace.

        This method performs the same dump operation as dump_workspace(), but runs
        the file I/O operations in a thread pool for better performance in async contexts.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
                  If empty, uses the current store_path.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist in memory.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(self.dump_workspace, workspace_id, path, callback_fn, **kwargs),
        )

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] = None,
        callback_fn=None,
        **kwargs,
    ):
        """
        Async version of load_workspace.

        This method performs the same load operation as load_workspace(), but runs
        the file I/O operations in a thread pool for better performance in async contexts.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
                  If empty, only loads from nodes parameter.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            C.thread_pool,
            partial(self.load_workspace, workspace_id, path, nodes, callback_fn, **kwargs),
        )

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """
        Async version of exist_workspace.

        This method performs the same check as exist_workspace() but is provided
        for consistency in async contexts.

        Args:
            workspace_id: Identifier of the workspace to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the workspace exists in memory, False otherwise.
        """
        return self.exist_workspace(workspace_id, **kwargs)

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of delete_workspace.

        This method performs the same delete operation as delete_workspace() but is
        provided for consistency in async contexts.

        Args:
            workspace_id: Identifier of the workspace to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        return self.delete_workspace(workspace_id, **kwargs)

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of create_workspace.

        This method performs the same create operation as create_workspace() but is
        provided for consistency in async contexts.

        Args:
            workspace_id: Identifier for the new workspace.
            **kwargs: Additional keyword arguments (unused).
        """
        return self.create_workspace(workspace_id, **kwargs)

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """
        Async version of delete.

        This method performs the same delete operation as delete() but is provided
        for consistency in async contexts.

        Args:
            node_ids: Single unique_id string or list of unique_id strings to delete.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
        return self.delete(node_ids, workspace_id, **kwargs)

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """
        Async version of copy_workspace.

        This method performs the same copy operation as copy_workspace() but is
        provided for consistency in async contexts.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist in memory.
        """
        return self.copy_workspace(src_workspace_id, dest_workspace_id, **kwargs)
