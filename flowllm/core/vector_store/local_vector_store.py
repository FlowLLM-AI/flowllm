"""
Local file-based vector store implementation.

This module provides a local file-based vector store that stores vector nodes
in JSONL format on disk. It supports workspace management, vector similarity search,
and provides both synchronous and asynchronous operations.
"""

import asyncio
import json
import math
from functools import partial
from pathlib import Path
from typing import List, Iterable, Optional, Dict, Any

from loguru import logger
from tqdm import tqdm

from .base_vector_store import BaseVectorStore
from ..context.service_context import C
from ..schema.vector_node import VectorNode

# fcntl is Unix/Linux specific, not available on Windows
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
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


@C.register_vector_store("local")
class LocalVectorStore(BaseVectorStore):
    """
    Local file-based vector store implementation.

    This vector store persists all data to JSONL files on disk, with each workspace
    stored as a separate file. It supports file locking for thread-safe operations
    (on Unix/Linux systems) and provides both synchronous and asynchronous APIs.

    Attributes:
        store_dir: Directory path where workspace files are stored.
                  Defaults to "./local_vector_store".
    """

    def __init__(self, store_dir: str = "./local_vector_store", **kwargs):
        """
        Initialize the vector store by creating the storage directory if it doesn't exist.

        Args:
            store_dir: Directory path where workspace files are stored.
            **kwargs: Additional keyword arguments passed to BaseVectorStore.
        """
        super().__init__(**kwargs)
        self.store_dir = store_dir
        store_path = Path(self.store_dir)
        store_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _load_from_path(workspace_id: str, path: str | Path, callback_fn=None, **kwargs) -> Iterable:
        """
        Load vector nodes from a JSONL file on disk.

        Args:
            workspace_id: Identifier for the workspace to load.
            path: Directory path containing the workspace file.
            callback_fn: Optional callback function to transform node dictionaries
                        before creating VectorNode instances.
            **kwargs: Additional keyword arguments to pass to VectorNode constructor.

        Note:
            This method uses file locking (shared lock) when available to ensure
            thread-safe reads. On Windows, file locking is disabled.
        """
        workspace_path = Path(path) / f"{workspace_id}.jsonl"
        if not workspace_path.exists():
            logger.warning(f"workspace_path={workspace_path} does not exist!")
            return

        with workspace_path.open() as f:
            _acquire_lock(f, fcntl.LOCK_SH if HAS_FCNTL else None)
            try:
                for line in tqdm(f, desc="load from path"):
                    if line.strip():
                        node_dict = json.loads(line.strip())
                        if callback_fn:
                            node: VectorNode = callback_fn(node_dict)
                            assert isinstance(node, VectorNode)
                        else:
                            node: VectorNode = VectorNode(**node_dict, **kwargs)
                        node.workspace_id = workspace_id
                        yield node

            finally:
                _release_lock(f)

    @staticmethod
    def _dump_to_path(
        nodes: Iterable[VectorNode],
        workspace_id: str,
        path: str | Path = "",
        callback_fn=None,
        ensure_ascii: bool = False,
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
                for node in tqdm(nodes, desc="dump to path"):
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

    @property
    def store_path(self) -> Path:
        """
        Get the storage directory path.

        Returns:
            Path object representing the storage directory.
        """
        return Path(self.store_dir)

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """
        Check if a workspace exists.

        Args:
            workspace_id: Identifier of the workspace to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the workspace file exists, False otherwise.
        """
        workspace_path = self.store_path / f"{workspace_id}.jsonl"
        return workspace_path.exists()

    def delete_workspace(self, workspace_id: str, **kwargs):
        """
        Delete a workspace and all its nodes.

        Args:
            workspace_id: Identifier of the workspace to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        workspace_path = self.store_path / f"{workspace_id}.jsonl"
        if workspace_path.is_file():
            workspace_path.unlink()

    def create_workspace(self, workspace_id: str, **kwargs):
        """
        Create a new empty workspace.

        Args:
            workspace_id: Identifier for the new workspace.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.
        """
        self._dump_to_path(nodes=[], workspace_id=workspace_id, path=self.store_path, **kwargs)

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces.

        Returns:
            List[str]: Workspace identifiers discovered in the storage directory.
        """
        return [p.stem for p in self.store_path.glob("*.jsonl") if p.is_file()]

    def iter_workspace_nodes(self, workspace_id: str, **kwargs) -> Iterable[VectorNode]:
        """
        Iterate over all nodes in a workspace.

        Args:
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to _load_from_path.

        Yields:
            VectorNode: Nodes from the workspace, one at a time.
        """
        yield from self._load_from_path(
            path=self.store_path,
            workspace_id=workspace_id,
            **kwargs,
        )

    def dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """
        Export a workspace to disk at the specified path.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
                  If empty, uses the current store_path.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist.
        """
        if not self.exist_workspace(workspace_id=workspace_id, **kwargs):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return {}

        return self._dump_to_path(
            nodes=self.iter_workspace_nodes(workspace_id=workspace_id, **kwargs),
            workspace_id=workspace_id,
            path=path,
            callback_fn=callback_fn,
            **kwargs,
        )

    def load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] = None,
        callback_fn=None,
        **kwargs,
    ):
        """
        Load a workspace from disk, optionally merging with provided nodes.

        This method replaces any existing workspace with the same ID, then loads
        nodes from the specified path and/or the provided nodes list.

        Args:
            workspace_id: Identifier for the workspace to create/load.
            path: Directory path containing the workspace file to load.
                  If empty, loads from the current store_path.
            nodes: Optional list of VectorNode instances to merge with loaded nodes.
            callback_fn: Optional callback function to transform node dictionaries.
            **kwargs: Additional keyword arguments to pass to load operations.

        Returns:
            dict: Dictionary with "size" key indicating total number of nodes loaded.
        """
        if self.exist_workspace(workspace_id, **kwargs):
            self.delete_workspace(workspace_id=workspace_id, **kwargs)
            logger.info(f"delete workspace_id={workspace_id}")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        for node in self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs):
            all_nodes.append(node)

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)
        return {"size": len(all_nodes)}

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """
        Copy all nodes from one workspace to another.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
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
            if len(nodes) >= 100:
                self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
                nodes.clear()

        if nodes:
            self.insert(nodes=nodes, workspace_id=dest_workspace_id, **kwargs)
        return {"size": node_size}

    @staticmethod
    def _matches_filters(node: VectorNode, filter_dict: dict = None) -> bool:
        """
        Check if a node matches all filters in filter_dict.

        Supports both term filters (exact value match) and range filters
        (gte, lte, gt, lt). Nested keys can be accessed using dot notation
        (e.g., "metadata.node_type").

        Args:
            node: VectorNode instance to check.
            filter_dict: Dictionary of filters to apply. Can contain:
                - Term filters: {"key": value} for exact matches
                - Range filters: {"key": {"gte": min, "lte": max}} for ranges
                - Nested keys: {"metadata.node_type": value}

        Returns:
            bool: True if node matches all filters, False otherwise.
                 Returns True if filter_dict is None or empty.
        """
        if not filter_dict:
            return True

        for key, filter_value in filter_dict.items():
            # Navigate nested keys (e.g., "metadata.node_type")
            value = node.metadata
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

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """
        Search for similar nodes using vector similarity.

        Args:
            query: Text query to search for.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of top_k most similar nodes, sorted by similarity score
                             (highest first). Each node has a "score" key added to its metadata.
        """
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
        """
        Insert or update nodes in a workspace.

        If a node with the same unique_id already exists, it will be updated.
        New nodes will be added. All nodes are embedded before insertion.

        Args:
            nodes: Single VectorNode or list of VectorNode instances to insert/update.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
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

        self._dump_to_path(
            nodes=list(all_node_dict.values()),
            workspace_id=workspace_id,
            path=self.store_path,
            **kwargs,
        )

        logger.info(
            f"update workspace_id={workspace_id} nodes.size={len(nodes)} all.size={len(all_node_dict)} "
            f"update_cnt={update_cnt}",
        )

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """
        Delete nodes from a workspace by their unique IDs.

        Args:
            node_ids: Single unique_id string or list of unique_id strings to delete.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
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
        async embedding generation and runs file I/O operations in a thread pool
        for better performance in async contexts.

        Args:
            query: Text query to search for.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of top_k most similar nodes, sorted by similarity score
                             (highest first). Each node has a "score" key added to its metadata.
        """
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # Load nodes asynchronously
        loop = asyncio.get_event_loop()
        nodes_iter = await loop.run_in_executor(
            C.thread_pool,
            partial(self._load_from_path, path=self.store_path, workspace_id=workspace_id, **kwargs),
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
        """
        Async version of insert using embedding model async capabilities.

        This method performs the same insert operation as insert(), but uses
        async embedding generation and runs file I/O operations in a thread pool
        for better performance in async contexts.

        Args:
            nodes: Single VectorNode or list of VectorNode instances to insert/update.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        # Use async embedding
        nodes = await self.embedding_model.get_node_embeddings_async(nodes)

        # Load existing nodes asynchronously
        loop = asyncio.get_event_loop()
        exist_nodes_iter = await loop.run_in_executor(
            C.thread_pool,
            partial(self._load_from_path, path=self.store_path, workspace_id=workspace_id),
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
            partial(
                self._dump_to_path,
                nodes=list(all_node_dict.values()),
                workspace_id=workspace_id,
                path=self.store_path,
                **kwargs,
            ),
        )

        logger.info(
            f"update workspace_id={workspace_id} nodes.size={len(nodes)} all.size={len(all_node_dict)} "
            f"update_cnt={update_cnt}",
        )
