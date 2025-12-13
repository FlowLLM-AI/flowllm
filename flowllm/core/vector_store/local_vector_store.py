"""
Local file-based vector store implementation.

This module provides a local file-based vector store that stores vector nodes
in JSONL format on disk. It extends MemoryVectorStore to provide persistence
while maintaining fast in-memory operations.
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from loguru import logger

from .memory_vector_store import MemoryVectorStore
from ..context.service_context import C
from ..schema.vector_node import VectorNode


@C.register_vector_store("local")
class LocalVectorStore(MemoryVectorStore):
    """
    Local file-based vector store implementation.

    This vector store extends MemoryVectorStore to persist all data to JSONL files
    on disk. Each workspace is stored as a separate file. It combines the fast
    in-memory operations of MemoryVectorStore with automatic file persistence.

    Attributes:
        store_dir: Directory path where workspace files are stored.
                  Defaults to "./local_vector_store".
    """

    # ==================== Initialization ====================

    def __init__(self, store_dir: str = "./local_vector_store", **kwargs):
        """
        Initialize the vector store by creating the storage directory if it doesn't exist.

        Args:
            store_dir: Directory path where workspace files are stored.
            **kwargs: Additional keyword arguments passed to MemoryVectorStore.
        """
        super().__init__(**kwargs)
        self.store_dir = store_dir
        store_path = Path(self.store_dir)
        store_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalVectorStore initialized with store_dir={self.store_dir}")

    @property
    def store_path(self) -> Path:
        """
        Get the storage directory path.

        Returns:
            Path object representing the storage directory.
        """
        return Path(self.store_dir)

    # ==================== Workspace Management Methods ====================

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """
        Check if a workspace exists (either in memory or on disk).

        Args:
            workspace_id: Identifier of the workspace to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the workspace exists in memory or on disk, False otherwise.
        """
        # Check memory first, then disk
        if super().exist_workspace(workspace_id, **kwargs):
            return True
        workspace_path = self.store_path / f"{workspace_id}.jsonl"
        return workspace_path.exists()

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """
        Async version of exist_workspace.

        Args:
            workspace_id: Identifier of the workspace to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the workspace exists in memory or on disk, False otherwise.
        """
        return self.exist_workspace(workspace_id, **kwargs)

    def delete_workspace(self, workspace_id: str, **kwargs):
        """
        Delete a workspace from both memory and disk.

        Args:
            workspace_id: Identifier of the workspace to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        # Delete from memory
        super().delete_workspace(workspace_id, **kwargs)
        # Delete from disk
        workspace_path = self.store_path / f"{workspace_id}.jsonl"
        if workspace_path.is_file():
            workspace_path.unlink()
            logger.info(f"Deleted workspace file: {workspace_path}")

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of delete_workspace.

        Args:
            workspace_id: Identifier of the workspace to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        return await self._run_sync_in_executor(self.delete_workspace, workspace_id, **kwargs)

    def create_workspace(self, workspace_id: str, **kwargs):
        """
        Create a new empty workspace in memory and on disk.

        Args:
            workspace_id: Identifier for the new workspace.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.
        """
        # Create in memory
        super().create_workspace(workspace_id, **kwargs)
        # Create empty file on disk
        self._dump_to_path(nodes=[], workspace_id=workspace_id, path=self.store_path, show_progress=False, **kwargs)

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of create_workspace.

        Args:
            workspace_id: Identifier for the new workspace.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.
        """
        return await self._run_sync_in_executor(self.create_workspace, workspace_id, **kwargs)

    def list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """
        List all nodes in a workspace.

        If the workspace is in memory, returns from memory. Otherwise, loads from disk.

        Args:
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to _load_from_path.

        Returns:
            List[VectorNode]: All nodes from the workspace.
        """
        # If in memory, return from memory
        if workspace_id in self._memory_store:
            return super().list_workspace_nodes(workspace_id, **kwargs)
        # Otherwise, load from disk
        return self._load_from_path(
            path=self.store_path,
            workspace_id=workspace_id,
            **kwargs,
        )

    async def async_list_workspace_nodes(self, workspace_id: str, **kwargs) -> List[VectorNode]:
        """
        Async version of list_workspace_nodes.

        Args:
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to _load_from_path.

        Returns:
            List[VectorNode]: All nodes from the workspace.
        """
        # If in memory, return from memory (fast path)
        if workspace_id in self._memory_store:
            return super().list_workspace_nodes(workspace_id, **kwargs)
        # Otherwise, load from disk asynchronously
        return await self._run_sync_in_executor(
            self._load_from_path,
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

        # Use provided path or default to store_path
        dump_path = path if path else self.store_path

        return self._dump_to_path(
            nodes=self.list_workspace_nodes(workspace_id=workspace_id, **kwargs),
            workspace_id=workspace_id,
            path=dump_path,
            callback_fn=callback_fn,
            **kwargs,
        )

    async def async_dump_workspace(self, workspace_id: str, path: str | Path = "", callback_fn=None, **kwargs):
        """
        Async version of dump_workspace.

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
        nodes: List[VectorNode] | None = None,
        callback_fn=None,
        **kwargs,
    ):
        """
        Load a workspace from disk into memory, optionally merging with provided nodes.

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
            logger.info(f"Deleted existing workspace_id={workspace_id}")

        # Create workspace in memory
        super().create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        # Load from path (use store_path if path is empty)
        load_path = path if path else self.store_path
        all_nodes.extend(
            self._load_from_path(path=load_path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs),
        )

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)

        return {"size": len(all_nodes)}

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: List[VectorNode] | None = None,
        callback_fn=None,
        **kwargs,
    ):
        """
        Async version of load_workspace.

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
            logger.warning(f"src_workspace_id={src_workspace_id} does not exist!")
            return {}

        if not self.exist_workspace(dest_workspace_id, **kwargs):
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        # Ensure source workspace is loaded into memory
        self._ensure_workspace_loaded(src_workspace_id, **kwargs)

        # Use parent's copy_workspace for in-memory copy
        result = super().copy_workspace(src_workspace_id, dest_workspace_id, **kwargs)

        # Persist destination workspace to disk
        self._persist_workspace(dest_workspace_id, **kwargs)

        return result

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
                  or empty dict if source workspace doesn't exist.
        """
        return await self._run_sync_in_executor(
            self.copy_workspace,
            src_workspace_id,
            dest_workspace_id,
            **kwargs,
        )

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces (from disk).

        Returns:
            List[str]: Workspace identifiers discovered in the storage directory.
        """
        return [p.stem for p in self.store_path.glob("*.jsonl") if p.is_file()]

    async def async_list_workspace(self, **kwargs) -> List[str]:
        """
        Async version of list_workspace.

        Returns:
            List[str]: Workspace identifiers discovered in the storage directory.
        """
        return await self._run_sync_in_executor(self.list_workspace, **kwargs)

    # ==================== Helper Methods ====================

    def _ensure_workspace_loaded(self, workspace_id: str, **kwargs):
        """
        Ensure a workspace is loaded into memory from disk if not already present.

        Args:
            workspace_id: Identifier of the workspace to load.
            **kwargs: Additional keyword arguments to pass to _load_from_path.
        """
        if workspace_id not in self._memory_store:
            nodes = self._load_from_path(path=self.store_path, workspace_id=workspace_id, **kwargs)
            self._memory_store[workspace_id] = {node.unique_id: node for node in nodes}

    async def _async_ensure_workspace_loaded(self, workspace_id: str, **kwargs):
        """
        Async version of _ensure_workspace_loaded.

        Args:
            workspace_id: Identifier of the workspace to load.
            **kwargs: Additional keyword arguments to pass to _load_from_path.
        """
        if workspace_id not in self._memory_store:
            nodes = await self._run_sync_in_executor(
                self._load_from_path,
                path=self.store_path,
                workspace_id=workspace_id,
                **kwargs,
            )
            self._memory_store[workspace_id] = {node.unique_id: node for node in nodes}

    def _persist_workspace(self, workspace_id: str, **kwargs):
        """
        Persist a workspace from memory to disk.

        Args:
            workspace_id: Identifier of the workspace to persist.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.
        """
        if workspace_id in self._memory_store:
            nodes = list(self._memory_store[workspace_id].values())
            self._dump_to_path(
                nodes=nodes,
                workspace_id=workspace_id,
                path=self.store_path,
                show_progress=False,
                **kwargs,
            )

    async def _async_persist_workspace(self, workspace_id: str, **kwargs):
        """
        Async version of _persist_workspace.

        Args:
            workspace_id: Identifier of the workspace to persist.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.
        """
        if workspace_id in self._memory_store:
            nodes = list(self._memory_store[workspace_id].values())
            await self._run_sync_in_executor(
                self._dump_to_path,
                nodes=nodes,
                workspace_id=workspace_id,
                path=self.store_path,
                show_progress=False,
                **kwargs,
            )

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
        Search for similar nodes using vector similarity.

        Loads workspace from disk if not in memory, then performs search.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of matching nodes sorted by similarity score.
        """
        # Ensure workspace is loaded into memory
        self._ensure_workspace_loaded(workspace_id, **kwargs)
        # Use parent's search implementation
        return super().search(query, workspace_id, top_k, filter_dict, **kwargs)

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """
        Async version of search.

        Args:
            query: Text query to search for. If empty/None, performs filter-only
                search without vector similarity.
            workspace_id: Identifier of the workspace to search in.
            top_k: Number of top results to return. Defaults to 1.
            filter_dict: Optional dictionary of filters to apply to nodes.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            List[VectorNode]: List of matching nodes sorted by similarity score.
        """
        # Ensure workspace is loaded into memory
        await self._async_ensure_workspace_loaded(workspace_id, **kwargs)
        # Use parent's async search implementation
        return await super().async_search(query, workspace_id, top_k, filter_dict, **kwargs)

    # ==================== Insert Methods ====================

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """
        Insert or update nodes in a workspace.

        Nodes are inserted into memory and then persisted to disk.

        Args:
            nodes: Single VectorNode or list of VectorNode instances to insert/update.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
        # Ensure workspace is loaded into memory first
        self._ensure_workspace_loaded(workspace_id, **kwargs)
        # Insert into memory
        super().insert(nodes, workspace_id, **kwargs)
        # Persist to disk
        self._persist_workspace(workspace_id, **kwargs)

    async def async_insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """
        Async version of insert.

        Args:
            nodes: Single VectorNode or list of VectorNode instances to insert/update.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
        # Ensure workspace is loaded into memory first
        await self._async_ensure_workspace_loaded(workspace_id, **kwargs)
        # Insert into memory using async embedding
        await super().async_insert(nodes, workspace_id, **kwargs)
        # Persist to disk
        await self._async_persist_workspace(workspace_id, **kwargs)

    # ==================== Delete Methods ====================

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

        # Ensure workspace is loaded into memory
        self._ensure_workspace_loaded(workspace_id, **kwargs)
        # Delete from memory
        super().delete(node_ids, workspace_id, **kwargs)
        # Persist to disk
        self._persist_workspace(workspace_id, **kwargs)

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """
        Async version of delete.

        Args:
            node_ids: Single unique_id string or list of unique_id strings to delete.
            workspace_id: Identifier of the workspace.
            **kwargs: Additional keyword arguments to pass to operations.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        # Ensure workspace is loaded into memory
        await self._async_ensure_workspace_loaded(workspace_id, **kwargs)
        # Delete from memory
        super().delete(node_ids, workspace_id, **kwargs)
        # Persist to disk
        await self._async_persist_workspace(workspace_id, **kwargs)
