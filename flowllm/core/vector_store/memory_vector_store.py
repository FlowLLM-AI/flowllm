"""
In-memory vector store implementation.

This module provides an in-memory vector store that keeps all data in memory
for fast access. It inherits from LocalVectorStore for utility methods and can
persist data to disk when needed via dump_workspace and load_workspace methods.
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Optional, Any, Iterable

from loguru import logger
from tqdm import tqdm

from .base_vector_store import BaseVectorStore
from ..context import C
from ..schema import VectorNode

# fcntl is Unix/Linux specific, not available on Windows
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    fcntl = None
    HAS_FCNTL = False
    logger.warning("fcntl module not available (Windows). File locking will be disabled.")


def _acquire_lock(file_obj, lock_type):
    """Acquire file lock if fcntl is available."""
    if HAS_FCNTL:
        fcntl.flock(file_obj, lock_type)


def _release_lock(file_obj):
    """Release file lock if fcntl is available."""
    if HAS_FCNTL:
        fcntl.flock(file_obj, fcntl.LOCK_UN)


@C.register_vector_store("memory")
class MemoryVectorStore(BaseVectorStore):
    """
    In-memory vector store that keeps all data in memory for fast access.

    This vector store keeps all data in memory and only persists to disk when
    dump_workspace is called. It can load previously saved data via load_workspace.
    Provides both synchronous and asynchronous APIs for all operations.
    """

    # ==================== Initialization ====================

    def __init__(self, **kwargs):
        """
        Initialize the memory vector store.

        Args:
            **kwargs: Keyword arguments passed to the parent BaseVectorStore class.
        """
        super().__init__(**kwargs)
        self._memory_store: Dict[str, Dict[str, VectorNode]] = {}

    # ==================== Static Helper Methods ====================

    @staticmethod
    def _load_from_path(
        path: str | Path,
        workspace_id: str,
        callback_fn=None,
        show_progress: bool = True,
        **kwargs,
    ) -> List[VectorNode]:
        """
        Load vector nodes from a JSONL file on disk.

        Args:
            path: Directory path containing the workspace file.
            workspace_id: Identifier for the workspace to load.
            callback_fn: Optional callback function to transform node dictionaries
                        before creating VectorNode instances.
            show_progress: Whether to show tqdm progress bar. Defaults to True.
            **kwargs: Additional keyword arguments to pass to VectorNode constructor.

        Returns:
            List[VectorNode]: List of loaded vector nodes.

        Note:
            This method uses file locking (shared lock) when available to ensure
            thread-safe reads. On Windows, file locking is disabled.
        """
        workspace_path = Path(path) / f"{workspace_id}.jsonl"
        if not workspace_path.exists():
            logger.warning(f"workspace_path={workspace_path} does not exist!")
            return []

        nodes = []
        with workspace_path.open() as f:
            _acquire_lock(f, fcntl.LOCK_SH if HAS_FCNTL else None)
            try:
                lines = tqdm(f, desc="load from path") if show_progress else f
                for line in lines:
                    if line.strip():
                        node_dict = json.loads(line.strip())
                        if callback_fn:
                            node: VectorNode = callback_fn(node_dict)
                            assert isinstance(node, VectorNode)
                        else:
                            node: VectorNode = VectorNode(**node_dict, **kwargs)
                        node.workspace_id = workspace_id
                        nodes.append(node)

            finally:
                _release_lock(f)
        return nodes

    @staticmethod
    def _dump_to_path(
        nodes: Iterable[VectorNode],
        workspace_id: str,
        path: str | Path = "",
        callback_fn=None,
        ensure_ascii: bool = False,
        show_progress: bool = True,
        **kwargs,
    ):
        """
        Write vector nodes to a JSONL file on disk.

        Args:
            nodes: Iterable of VectorNode instances to write.
            workspace_id: Identifier for the workspace.
            path: Directory path where the workspace file should be written.
            callback_fn: Optional callback function to transform VectorNode instances
                        before serialization.
            ensure_ascii: If True, ensure all non-ASCII characters are escaped.
                         Defaults to False.
            show_progress: Whether to show tqdm progress bar. Defaults to True.
            **kwargs: Additional keyword arguments to pass to json.dumps.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes written.

        Note:
            This method uses file locking (exclusive lock) when available to ensure
            thread-safe writes. On Windows, file locking is disabled.
        """
        dump_path: Path = Path(path)
        dump_path.mkdir(parents=True, exist_ok=True)
        dump_file = dump_path / f"{workspace_id}.jsonl"

        count = 0
        with dump_file.open("w") as f:
            _acquire_lock(f, fcntl.LOCK_EX if HAS_FCNTL else None)
            try:
                nodes_iter = tqdm(nodes, desc="dump to path") if show_progress else nodes
                for node in nodes_iter:
                    node.workspace_id = workspace_id
                    if callback_fn:
                        node_dict = callback_fn(node)
                        assert isinstance(node_dict, dict)
                    else:
                        node_dict = node.model_dump()

                    f.write(json.dumps(node_dict, ensure_ascii=ensure_ascii, **kwargs))
                    f.write("\n")
                    count += 1

                return {"size": count}
            finally:
                _release_lock(f)

    @staticmethod
    def _matches_filters(node: VectorNode, filter_dict: dict = None) -> bool:
        """
        Check if a node matches all filters in filter_dict.

        Supports both term filters (exact value match) and range filters
        (gte, lte, gt, lt). Keys can access both top-level VectorNode fields
        (unique_id, workspace_id, content) and nested metadata using dot notation
        (e.g., "metadata.node_type").

        Args:
            node: VectorNode instance to check.
            filter_dict: Dictionary of filters to apply. Can contain:
                - Term filters: {"key": value} for exact matches
                - Range filters: {"key": {"gte": min, "lte": max}} for ranges
                - Top-level keys: {"unique_id": value, "content": value}
                - Nested keys: {"metadata.node_type": value}

        Returns:
            bool: True if node matches all filters, False otherwise.
                 Returns True if filter_dict is None or empty.
        """
        if not filter_dict:
            return True

        # Convert node to dict for unified access to all fields
        node_dict = node.model_dump()

        for key, filter_value in filter_dict.items():
            # Navigate nested keys (e.g., "metadata.node_type")
            value = node_dict
            key_found = True
            for key_part in key.split("."):
                if isinstance(value, dict) and key_part in value:
                    value = value[key_part]
                else:
                    key_found = False
                    break

            if not key_found:
                return False

            # Handle different filter types
            if isinstance(filter_value, dict):
                # Range filter: {"gte": 1, "lte": 10}
                range_match = True
                if "gte" in filter_value and value < filter_value["gte"]:
                    range_match = False
                elif "lte" in filter_value and value > filter_value["lte"]:
                    range_match = False
                elif "gt" in filter_value and value <= filter_value["gt"]:
                    range_match = False
                elif "lt" in filter_value and value >= filter_value["lt"]:
                    range_match = False
                if not range_match:
                    return False
            elif isinstance(filter_value, list):
                # List filter: value must match any item in the list (OR logic)
                if value not in filter_value:
                    return False
            else:
                # Term filter: direct value comparison
                if value != filter_value:
                    return False

        return True

    @staticmethod
    def calculate_similarity(query_vector: List[float], node_vector: List[float]):
        """
        Calculate cosine similarity between two vectors.

        Args:
            query_vector: Query embedding vector.
            node_vector: Node embedding vector.

        Returns:
            float: Cosine similarity score between -1 and 1 (typically 0-1 for normalized vectors).

        Raises:
            AssertionError: If vectors are empty or have different dimensions.
        """
        assert query_vector, "query_vector is empty!"
        assert node_vector, "node_vector is empty!"
        assert len(query_vector) == len(
            node_vector,
        ), f"query_vector.size={len(query_vector)} node_vector.size={len(node_vector)}"

        dot_product = sum(x * y for x, y in zip(query_vector, node_vector))
        norm_v1 = math.sqrt(sum(x**2 for x in query_vector))
        norm_v2 = math.sqrt(sum(y**2 for y in node_vector))
        return dot_product / (norm_v1 * norm_v2)

    # ==================== Workspace Management Methods ====================

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

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """
        Async version of exist_workspace.

        Args:
            workspace_id: Identifier of the workspace to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the workspace exists in memory, False otherwise.
        """
        return self.exist_workspace(workspace_id, **kwargs)

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

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of delete_workspace.

        Args:
            workspace_id: Identifier of the workspace to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        return self.delete_workspace(workspace_id, **kwargs)

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

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of create_workspace.

        Args:
            workspace_id: Identifier for the new workspace.
            **kwargs: Additional keyword arguments (unused).
        """
        return self.create_workspace(workspace_id, **kwargs)

    def list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """
        List all nodes in a workspace.

        Args:
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List[VectorNode]: All nodes from the workspace, or empty list if workspace doesn't exist.
        """
        if workspace_id in self._memory_store:
            return list(self._memory_store[workspace_id].values())
        return []

    async def async_list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """
        Async version of list_workspace_nodes.

        Args:
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List[VectorNode]: All nodes from the workspace, or empty list if workspace doesn't exist.
        """
        return self.list_workspace_nodes(workspace_id, **kwargs)

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """
        Export a workspace from memory to disk at the specified path.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist in memory or path is empty.
        """
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return {}

        if not path:
            logger.warning("path is empty, cannot dump workspace!")
            return {}

        nodes = list(self._memory_store[workspace_id].values())

        return self._dump_to_path(
            nodes=nodes,
            workspace_id=workspace_id,
            path=path,
            callback_fn=callback_fn,
            **kwargs,
        )

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """
        Async version of dump_workspace.

        This method performs the same dump operation as dump_workspace(), but runs
        the file I/O operations in a thread pool for better performance in async contexts.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist in memory or path is empty.
        """
        return await self._run_sync_in_executor(
            self.dump_workspace,
            workspace_id,
            path,
            callback_fn,
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

        if path:
            all_nodes.extend(
                self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs),
            )

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)

        logger.info(f"Loaded workspace_id={workspace_id} with {len(all_nodes)} nodes into memory")
        return {"size": len(all_nodes)}

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: Optional[List[VectorNode]] = None,
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
        return await self._run_sync_in_executor(
            self.load_workspace,
            workspace_id,
            path,
            nodes,
            callback_fn,
            **kwargs,
        )

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

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """
        Async version of copy_workspace.

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

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces in memory.

        Returns:
            List[str]: Workspace identifiers currently present in memory.
        """
        return list(self._memory_store.keys())

    async def async_list_workspace(self, **kwargs) -> List[str]:
        """
        Async version of list_workspace.

        Returns:
            List[str]: Workspace identifiers currently present in memory.
        """
        return self.list_workspace(**kwargs)

    # ==================== Search Methods ====================

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

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of matching nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a
                "score" key in metadata. When query is empty, nodes are returned
                in storage order without scores.
        """
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return []

        # When query is empty, degrade to filter-only search without vector similarity
        use_vector_search = bool(query)
        query_vector = self.get_embeddings(query) if use_vector_search else None

        nodes: List[VectorNode] = []

        for node in self._memory_store[workspace_id].values():
            # Apply filters
            if self._matches_filters(node, filter_dict):
                if use_vector_search:
                    if node.vector:
                        score = self.calculate_similarity(query_vector, node.vector)
                        result_node = VectorNode(**node.model_dump())
                        result_node.metadata["score"] = score
                        nodes.append(result_node)
                else:
                    nodes.append(node)
                    # Early exit for filter-only search when we have enough results
                    if len(nodes) >= top_k:
                        break

        # Only sort by score when using vector search
        if use_vector_search:
            nodes = sorted(nodes, key=lambda x: x.metadata["score"], reverse=True)

        return nodes[:top_k]

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

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of matching nodes. When query is provided,
                nodes are sorted by similarity score (highest first) with a
                "score" key in metadata. When query is empty, nodes are returned
                in storage order without scores.
        """
        if workspace_id not in self._memory_store:
            logger.warning(f"workspace_id={workspace_id} not found in memory!")
            return []

        # When query is empty, degrade to filter-only search without vector similarity
        use_vector_search = bool(query)
        query_vector = await self.async_get_embeddings(query) if use_vector_search else None

        nodes: List[VectorNode] = []

        for node in self._memory_store[workspace_id].values():
            # Apply filters
            if self._matches_filters(node, filter_dict):
                if use_vector_search:
                    if node.vector:
                        score = self.calculate_similarity(query_vector, node.vector)
                        result_node = VectorNode(**node.model_dump())
                        result_node.metadata["score"] = score
                        nodes.append(result_node)
                else:
                    nodes.append(node)
                    # Early exit for filter-only search when we have enough results
                    if len(nodes) >= top_k:
                        break

        # Only sort by score when using vector search
        if use_vector_search:
            nodes = sorted(nodes, key=lambda x: x.metadata["score"], reverse=True)

        return nodes[:top_k]

    # ==================== Insert Methods ====================

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

        nodes: List[VectorNode] = self.get_node_embeddings(nodes)

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
        nodes = await self.async_get_node_embeddings(nodes)

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

    # ==================== Delete Methods ====================

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

    # ==================== Close Methods ====================

    def close(self):
        """
        Close the vector store and clean up resources.

        For MemoryVectorStore, this clears all data from memory.
        """
        self._memory_store.clear()

    async def async_close(self):
        """
        Async version of close.

        For MemoryVectorStore, this clears all data from memory.
        """
        self.close()
