"""PostgreSQL pgvector vector store implementation.

This module provides a PostgreSQL-based vector store that stores vector nodes
in PostgreSQL tables using the pgvector extension. It supports workspace management,
vector similarity search, metadata filtering using SQL WHERE clauses, and provides
both synchronous and asynchronous operations using psycopg and asyncpg.
"""

# pylint: disable=too-many-lines

import json
import os
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from loguru import logger

from .memory_vector_store import MemoryVectorStore
from ..context import C
from ..schema import VectorNode


@C.register_vector_store("pgvector")
class PgVectorStore(MemoryVectorStore):
    """PostgreSQL pgvector vector store implementation.

    This class provides a vector store backend using PostgreSQL with the pgvector
    extension for storing and searching vector embeddings. It supports both synchronous
    and asynchronous operations using psycopg and asyncpg, and includes metadata
    filtering capabilities using SQL WHERE clauses.

    Attributes:
        connection_string: PostgreSQL connection string for synchronous operations.
            Defaults to the FLOW_PGVECTOR_CONNECTION_STRING environment variable
            or "postgresql://localhost/postgres".
        async_connection_string: PostgreSQL connection string for asynchronous operations.
            Defaults to the FLOW_PGVECTOR_ASYNC_CONNECTION_STRING environment variable
            or None (will use connection_string with asyncpg).
        batch_size: Batch size for bulk operations. Defaults to 1024.
    """

    # ==================== Initialization ====================

    def __init__(
        self,
        connection_string: str | None = None,
        async_connection_string: str | None = None,
        batch_size: int = 1024,
        **kwargs,
    ):
        """Initialize PostgreSQL connections.

        Args:
            connection_string: PostgreSQL connection string for synchronous operations.
            async_connection_string: PostgreSQL connection string for asynchronous operations.
            batch_size: Batch size for bulk operations.
            **kwargs: Additional keyword arguments passed to MemoryVectorStore.
        """
        super().__init__(**kwargs)
        self.connection_string = connection_string or os.getenv(
            "FLOW_PGVECTOR_CONNECTION_STRING",
            "postgresql://localhost/postgres",
        )
        self.async_connection_string = async_connection_string or os.getenv(
            "FLOW_PGVECTOR_ASYNC_CONNECTION_STRING",
        )
        self.batch_size = batch_size

        # Initialize synchronous connection
        import psycopg

        self._conn = psycopg.connect(self.connection_string)
        self._conn.autocommit = False

        # Initialize async connection (created lazily in async methods)
        self._async_conn = None
        # Use async_connection_string if provided, otherwise use connection_string
        # asyncpg accepts standard postgresql:// connection strings directly
        self._async_conn_string = self.async_connection_string or self.connection_string

        # Ensure pgvector extension exists
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self._conn.commit()

        logger.info(
            f"PostgreSQL pgvector client initialized with connection_string={self.connection_string}",
        )

    # ==================== Static Helper Methods ====================

    @staticmethod
    def _get_table_name(workspace_id: str) -> str:
        """Get the table name for a workspace.

        Args:
            workspace_id: The workspace identifier.

        Returns:
            str: The table name (sanitized workspace_id).
        """
        # Sanitize workspace_id to be a valid PostgreSQL identifier
        # Replace non-alphanumeric characters with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", workspace_id)
        return f"workspace_{sanitized}"

    @staticmethod
    def _row2node(row: Tuple, workspace_id: str) -> VectorNode:
        """Convert a PostgreSQL row to a VectorNode.

        Args:
            row: The PostgreSQL row tuple (unique_id, workspace_id, content, metadata, vector::text).
            workspace_id: The workspace identifier to assign to the node.

        Returns:
            VectorNode: A VectorNode instance created from the row data.
        """
        unique_id, workspace_id_col, content, metadata, vector_str = row
        # Parse vector string (format: [0.1,0.2,0.3] from pgvector)
        # pgvector returns vector as string like '[0.1,0.2,0.3]'
        vector = json.loads(vector_str)

        # Parse metadata if it's a string (psycopg may return JSONB as string in some cases)
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        elif metadata is None:
            metadata = {}

        node = VectorNode(
            unique_id=unique_id,
            workspace_id=workspace_id_col or workspace_id,
            content=content,
            metadata=metadata,
            vector=vector,
        )
        return node

    @staticmethod
    def _build_sql_filters(
        filter_dict: Optional[Dict[str, Any]] = None,
        use_async: bool = False,
    ) -> Tuple[str, List[Any]]:
        """Build SQL WHERE clause from filter_dict.

        Converts a filter dictionary into SQL WHERE conditions.
        Supports both term filters (exact match) and range filters (gte, lte, gt, lt).

        Args:
            filter_dict: Dictionary of filter conditions. Keys are metadata field names,
                values can be exact match values or range dictionaries like
                {"gte": 1, "lte": 10}.
                - Keys starting with "metadata." will have the prefix stripped
                - "unique_id" is treated as a direct column reference
            use_async: If True, use asyncpg-style placeholders ($1, $2), else use psycopg-style (%s).

        Returns:
            Tuple[str, List[Any]]: SQL WHERE clause string and list of parameters.
        """
        if not filter_dict:
            return "", []

        conditions = []
        params = []
        param_idx = 1

        for key, filter_value in filter_dict.items():
            # Handle special keys that are stored as direct columns
            if key == "unique_id":
                # unique_id is a direct column, not in metadata JSONB
                if use_async:
                    conditions.append(f"unique_id = ${param_idx}")
                else:
                    conditions.append("unique_id = %s")
                params.append(str(filter_value))
                param_idx += 1
                continue

            # Strip "metadata." prefix if present (since we're already accessing metadata column)
            if key.startswith("metadata."):
                metadata_key = key[len("metadata.") :]
            else:
                metadata_key = key

            # Handle nested keys by using JSONB path operators
            jsonb_path = f"metadata->>'{metadata_key}'"

            if isinstance(filter_value, dict):
                # Range filter: {"gte": 1, "lte": 10}
                range_conditions = []
                if "gte" in filter_value:
                    if use_async:
                        range_conditions.append(f"({jsonb_path}::numeric) >= ${param_idx}")
                    else:
                        range_conditions.append(f"({jsonb_path}::numeric) >= %s")
                    params.append(filter_value["gte"])
                    param_idx += 1
                if "lte" in filter_value:
                    if use_async:
                        range_conditions.append(f"({jsonb_path}::numeric) <= ${param_idx}")
                    else:
                        range_conditions.append(f"({jsonb_path}::numeric) <= %s")
                    params.append(filter_value["lte"])
                    param_idx += 1
                if "gt" in filter_value:
                    if use_async:
                        range_conditions.append(f"({jsonb_path}::numeric) > ${param_idx}")
                    else:
                        range_conditions.append(f"({jsonb_path}::numeric) > %s")
                    params.append(filter_value["gt"])
                    param_idx += 1
                if "lt" in filter_value:
                    if use_async:
                        range_conditions.append(f"({jsonb_path}::numeric) < ${param_idx}")
                    else:
                        range_conditions.append(f"({jsonb_path}::numeric) < %s")
                    params.append(filter_value["lt"])
                    param_idx += 1
                if range_conditions:
                    conditions.append(f"({' AND '.join(range_conditions)})")
            elif isinstance(filter_value, list):
                # List filter: use IN clause for OR logic
                if use_async:
                    placeholders = ", ".join(f"${param_idx + i}" for i in range(len(filter_value)))
                    conditions.append(f"{jsonb_path} IN ({placeholders})")
                else:
                    placeholders = ", ".join(["%s"] * len(filter_value))
                    conditions.append(f"{jsonb_path} IN ({placeholders})")
                params.extend([str(v) for v in filter_value])
                param_idx += len(filter_value)
            else:
                # Term filter: direct value comparison
                if use_async:
                    conditions.append(f"{jsonb_path} = ${param_idx}")
                else:
                    conditions.append(f"{jsonb_path} = %s")
                params.append(str(filter_value))
                param_idx += 1

        where_clause = " AND ".join(conditions)
        return where_clause, params

    # ==================== Workspace Management Methods ====================

    def exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a PostgreSQL table (workspace) exists.

        Args:
            workspace_id: The identifier of the workspace/table to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the table exists, False otherwise.
        """
        table_name = self._get_table_name(workspace_id)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
                """,
                (table_name,),
            )
            return cur.fetchone()[0]

    async def async_exist_workspace(self, workspace_id: str, **kwargs) -> bool:
        """Check if a PostgreSQL table (workspace) exists (async).

        Args:
            workspace_id: The identifier of the workspace/table to check.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            bool: True if the table exists, False otherwise.
        """
        table_name = self._get_table_name(workspace_id)
        conn = await self._get_async_conn()
        result = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = $1
            )
            """,
            table_name,
        )
        return result

    def delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a PostgreSQL table (workspace).

        Args:
            workspace_id: The identifier of the workspace/table to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        table_name = self._get_table_name(workspace_id)
        with self._conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
            self._conn.commit()
        logger.info(f"Deleted workspace table: {table_name}")

    async def async_delete_workspace(self, workspace_id: str, **kwargs):
        """Delete a PostgreSQL table (workspace) (async).

        Args:
            workspace_id: The identifier of the workspace/table to delete.
            **kwargs: Additional keyword arguments (unused).
        """
        table_name = self._get_table_name(workspace_id)
        logger.debug(f"Attempting to delete workspace table: {table_name}")
        conn = await self._get_async_conn()
        logger.debug(f"Connection established, executing DROP TABLE for {table_name}")
        await conn.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        logger.info(f"Successfully deleted workspace table: {table_name}")

    def create_workspace(self, workspace_id: str, **kwargs):
        """Create a new PostgreSQL table (workspace) with vector field.

        Args:
            workspace_id: The identifier of the workspace/table to create.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            The response from PostgreSQL create table statement.
        """
        table_name = self._get_table_name(workspace_id)
        dimensions = self.embedding_model.dimensions

        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS "{table_name}" (
                    unique_id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    vector vector({dimensions}) NOT NULL
                )
                """,
            )
            # Create index for vector similarity search using HNSW
            # HNSW is preferred over IVFFlat as it works with any dataset size
            # and provides better recall with similar performance
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS "{table_name}_vector_idx"
                ON "{table_name}" USING hnsw (vector vector_cosine_ops)
                """,
            )
            # Create index for metadata filtering
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS "{table_name}_metadata_idx"
                ON "{table_name}" USING gin (metadata)
                """,
            )
            self._conn.commit()
        logger.info(f"Created workspace table: {table_name} with vector({dimensions})")

    async def async_create_workspace(self, workspace_id: str, **kwargs):
        """Create a new PostgreSQL table (workspace) with vector field (async).

        Args:
            workspace_id: The identifier of the workspace/table to create.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            The response from PostgreSQL create table statement.
        """
        table_name = self._get_table_name(workspace_id)
        dimensions = self.embedding_model.dimensions

        conn = await self._get_async_conn()
        await conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                unique_id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB NOT NULL,
                vector vector({dimensions}) NOT NULL
            )
            """,
        )
        # Create index for vector similarity search using HNSW
        # HNSW is preferred over IVFFlat as it works with any dataset size
        # and provides better recall with similar performance
        await conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS "{table_name}_vector_idx"
            ON "{table_name}" USING hnsw (vector vector_cosine_ops)
            """,
        )
        # Create index for metadata filtering
        await conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS "{table_name}_metadata_idx"
            ON "{table_name}" USING gin (metadata)
            """,
        )
        logger.info(f"Created workspace table: {table_name} with vector({dimensions})")

    def list_workspace_nodes(
        self,
        workspace_id: str,
        max_size: int = 10000,
        **kwargs,
    ) -> List[VectorNode]:
        """List all nodes in a workspace.

        Args:
            workspace_id: The identifier of the workspace to iterate over.
            max_size: Maximum number of nodes to retrieve (default: 10000).
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List[VectorNode]: Vector nodes from the workspace.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        table_name = self._get_table_name(workspace_id)
        nodes: List[VectorNode] = []
        with self._conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT unique_id, workspace_id, content, metadata, vector::text
                FROM "{table_name}"
                LIMIT %s
                """,
                (max_size,),
            )
            for row in cur.fetchall():
                node = self._row2node(row, workspace_id)
                nodes.append(node)
        return nodes

    async def async_list_workspace_nodes(
        self,
        workspace_id: str,
        max_size: int = 10000,
        **kwargs,
    ) -> List[VectorNode]:
        """List all nodes in a workspace (async).

        Args:
            workspace_id: The identifier of the workspace to iterate over.
            max_size: Maximum number of nodes to retrieve (default: 10000).
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List[VectorNode]: Vector nodes from the workspace.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        table_name = self._get_table_name(workspace_id)
        conn = await self._get_async_conn()
        rows = await conn.fetch(
            f"""
            SELECT unique_id, workspace_id, content, metadata, vector::text
            FROM "{table_name}"
            LIMIT $1
            """,
            max_size,
        )

        nodes: List[VectorNode] = []
        for row in rows:
            unique_id = row["unique_id"]
            workspace_id_col = row["workspace_id"]
            content = row["content"]
            metadata = row["metadata"]
            vector_str = row["vector"]

            # Parse vector string (format: [0.1,0.2,0.3] from pgvector)
            vector = json.loads(vector_str)

            # Parse metadata if it's a string
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            elif metadata is None:
                metadata = {}

            node = VectorNode(
                unique_id=unique_id,
                workspace_id=workspace_id_col or workspace_id,
                content=content,
                metadata=metadata,
                vector=vector,
            )
            nodes.append(node)

        return nodes

    def dump_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        callback_fn=None,
        **kwargs,
    ):
        """Export a workspace from PostgreSQL to disk at the specified path.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist or path is empty.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return {}

        if not path:
            logger.warning("path is empty, cannot dump workspace!")
            return {}

        nodes = self.list_workspace_nodes(workspace_id=workspace_id, **kwargs)

        return self._dump_to_path(
            nodes=nodes,
            workspace_id=workspace_id,
            path=path,
            callback_fn=callback_fn,
            **kwargs,
        )

    async def async_dump_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        callback_fn=None,
        **kwargs,
    ):
        """Async version of dump_workspace.

        Args:
            workspace_id: Identifier of the workspace to export.
            path: Directory path where to write the exported workspace file.
            callback_fn: Optional callback function to transform nodes during export.
            **kwargs: Additional keyword arguments to pass to _dump_to_path.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes exported,
                  or empty dict if workspace doesn't exist or path is empty.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return {}

        if not path:
            logger.warning("path is empty, cannot dump workspace!")
            return {}

        nodes = await self.async_list_workspace_nodes(workspace_id=workspace_id, **kwargs)

        return await self._run_sync_in_executor(
            self._dump_to_path,
            nodes=nodes,
            workspace_id=workspace_id,
            path=path,
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
        """Load a workspace into PostgreSQL from disk, optionally merging with provided nodes.

        This method replaces any existing workspace with the same ID,
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
        if self.exist_workspace(workspace_id=workspace_id):
            self.delete_workspace(workspace_id=workspace_id)
            logger.info(f"Deleted existing workspace_id={workspace_id}")

        self.create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        if path:
            all_nodes.extend(
                self._load_from_path(
                    path=path,
                    workspace_id=workspace_id,
                    callback_fn=callback_fn,
                    **kwargs,
                ),
            )

        if all_nodes:
            self.insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)

        logger.info(f"Loaded workspace_id={workspace_id} with {len(all_nodes)} nodes into PostgreSQL")
        return {"size": len(all_nodes)}

    async def async_load_workspace(
        self,
        workspace_id: str,
        path: str | Path = "",
        nodes: Optional[List[VectorNode]] = None,
        callback_fn=None,
        **kwargs,
    ):
        """Async version of load_workspace.

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
        if await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_delete_workspace(workspace_id=workspace_id)
            logger.info(f"Deleted existing workspace_id={workspace_id}")

        await self.async_create_workspace(workspace_id=workspace_id, **kwargs)

        all_nodes: List[VectorNode] = []

        if nodes:
            all_nodes.extend(nodes)

        if path:
            loaded_nodes = await self._run_sync_in_executor(
                lambda: list(
                    self._load_from_path(path=path, workspace_id=workspace_id, callback_fn=callback_fn, **kwargs),
                ),
            )
            all_nodes.extend(loaded_nodes)

        if all_nodes:
            await self.async_insert(nodes=all_nodes, workspace_id=workspace_id, **kwargs)

        logger.info(f"Loaded workspace_id={workspace_id} with {len(all_nodes)} nodes into PostgreSQL")
        return {"size": len(all_nodes)}

    def copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Copy all nodes from one workspace to another in PostgreSQL.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
        if not self.exist_workspace(workspace_id=src_workspace_id):
            logger.warning(f"src_workspace_id={src_workspace_id} does not exist!")
            return {}

        if not self.exist_workspace(workspace_id=dest_workspace_id):
            self.create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = self.list_workspace_nodes(workspace_id=src_workspace_id, **kwargs)
        node_size = len(src_nodes)

        new_nodes = []
        for node in src_nodes:
            new_node = VectorNode(**node.model_dump())
            new_node.workspace_id = dest_workspace_id
            new_nodes.append(new_node)

        if new_nodes:
            self.insert(nodes=new_nodes, workspace_id=dest_workspace_id, **kwargs)

        logger.info(f"Copied {node_size} nodes from {src_workspace_id} to {dest_workspace_id}")
        return {"size": node_size}

    async def async_copy_workspace(self, src_workspace_id: str, dest_workspace_id: str, **kwargs):
        """Async version of copy_workspace.

        Args:
            src_workspace_id: Identifier of the source workspace.
            dest_workspace_id: Identifier of the destination workspace.
                              Created if it doesn't exist.
            **kwargs: Additional keyword arguments to pass to operations.

        Returns:
            dict: Dictionary with "size" key indicating number of nodes copied,
                  or empty dict if source workspace doesn't exist.
        """
        if not await self.async_exist_workspace(workspace_id=src_workspace_id):
            logger.warning(f"src_workspace_id={src_workspace_id} does not exist!")
            return {}

        if not await self.async_exist_workspace(workspace_id=dest_workspace_id):
            await self.async_create_workspace(workspace_id=dest_workspace_id, **kwargs)

        src_nodes = await self.async_list_workspace_nodes(workspace_id=src_workspace_id, **kwargs)
        node_size = len(src_nodes)

        new_nodes = []
        for node in src_nodes:
            new_node = VectorNode(**node.model_dump())
            new_node.workspace_id = dest_workspace_id
            new_nodes.append(new_node)

        if new_nodes:
            await self.async_insert(nodes=new_nodes, workspace_id=dest_workspace_id, **kwargs)

        logger.info(f"Copied {node_size} nodes from {src_workspace_id} to {dest_workspace_id}")
        return {"size": node_size}

    def list_workspace(self, **kwargs) -> List[str]:
        """List all existing workspaces (tables) in PostgreSQL.

        Returns:
            List[str]: Workspace identifiers (table names without prefix).
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name LIKE 'workspace_%'
                ORDER BY table_name
                """,
            )
            table_names = [row[0] for row in cur.fetchall()]
            # Remove 'workspace_' prefix
            workspace_ids = [name.replace("workspace_", "", 1) for name in table_names]
            return workspace_ids

    async def async_list_workspace(self, **kwargs) -> List[str]:
        """Async version of list_workspace.

        Returns:
            List[str]: Workspace identifiers (table names without prefix).
        """
        conn = await self._get_async_conn()
        rows = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE 'workspace_%'
            ORDER BY table_name
            """,
        )
        table_names = [row["table_name"] for row in rows]
        # Remove 'workspace_' prefix
        workspace_ids = [name.replace("workspace_", "", 1) for name in table_names]
        return workspace_ids

    # ==================== Search Methods ====================

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity.

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model. If empty/None, performs filter-only search.
            workspace_id: The identifier of the workspace to search in.
            top_k: Maximum number of results to return (default: 1).
            filter_dict: Optional dictionary of metadata filters to apply.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List[VectorNode]: List of matching vector nodes sorted by similarity score.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Build filters from filter_dict
        where_clause, filter_params = self._build_sql_filters(filter_dict)
        table_name = self._get_table_name(workspace_id)
        where_sql = f"WHERE {where_clause}" if where_clause else ""

        # When query is empty, degrade to filter-only search without vector similarity
        use_vector_search = bool(query)

        if use_vector_search:
            query_vector = self.get_embeddings(query)
            # Convert query_vector to string format for pgvector
            query_vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

            with self._conn.cursor() as cur:
                # Build SQL with correct parameter order matching SQL clause order:
                # 1. %s::vector in SELECT (for score calculation)
                # 2. filter_params in WHERE clause
                # 3. %s::vector in ORDER BY
                # 4. %s for LIMIT
                cur.execute(
                    f"""
                    SELECT unique_id, workspace_id, content, metadata, vector::text,
                           1 - (vector <=> %s::vector) AS score
                    FROM "{table_name}"
                    {where_sql}
                    ORDER BY vector <=> %s::vector
                    LIMIT %s
                    """,
                    [query_vector_str] + filter_params + [query_vector_str, top_k],
                )

                nodes: List[VectorNode] = []
                for row in cur.fetchall():
                    unique_id, workspace_id_col, content, metadata, vector_str, score = row
                    # Parse vector string (format: [0.1,0.2,0.3] from pgvector)
                    vector = json.loads(vector_str)

                    # Parse metadata if it's a string
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    elif metadata is None:
                        metadata = {}

                    node = VectorNode(
                        unique_id=unique_id,
                        workspace_id=workspace_id_col or workspace_id,
                        content=content,
                        metadata=metadata,
                        vector=vector,
                    )
                    node.metadata["score"] = float(score)
                    nodes.append(node)

                return nodes
        else:
            # Filter-only search without vector similarity
            with self._conn.cursor() as cur:
                # Parameters: filter_params first, then top_k
                cur.execute(
                    f"""
                    SELECT unique_id, workspace_id, content, metadata, vector::text
                    FROM "{table_name}"
                    {where_sql}
                    LIMIT %s
                    """,
                    filter_params + [top_k],
                )

                nodes: List[VectorNode] = []
                for row in cur.fetchall():
                    node = self._row2node(row, workspace_id)
                    nodes.append(node)

                return nodes

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity (async).

        When query is empty (empty string or None), the search degrades to a
        filter-only search without vector similarity ranking.

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model's async method. If empty/None, performs filter-only search.
            workspace_id: The identifier of the workspace to search in.
            top_k: Maximum number of results to return (default: 1).
            filter_dict: Optional dictionary of metadata filters to apply.
            **kwargs: Additional keyword arguments (unused).

        Returns:
            List[VectorNode]: List of matching vector nodes sorted by similarity score.
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return []

        # Build filters from filter_dict (use asyncpg-style placeholders)
        where_clause, filter_params = self._build_sql_filters(filter_dict, use_async=True)
        table_name = self._get_table_name(workspace_id)

        conn = await self._get_async_conn()

        # When query is empty, degrade to filter-only search without vector similarity
        use_vector_search = bool(query)

        if use_vector_search:
            # Use async embedding
            query_vector = await self.async_get_embeddings(query)
            # Convert query_vector to string format for pgvector
            query_vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

            # Build parameter list and adjust placeholder indices
            # $1 is for query_vector, so filter_params start from $2
            if filter_params:
                adjusted_where = where_clause
                # Replace placeholders in reverse order to avoid $1 being replaced when replacing $10
                for i in range(len(filter_params) - 1, -1, -1):
                    old_placeholder = f"${i + 1}"
                    new_placeholder = f"${i + 2}"  # Shift by 1 since $1 is query_vector
                    adjusted_where = adjusted_where.replace(old_placeholder, new_placeholder)
                where_sql = f"WHERE {adjusted_where}"
            else:
                where_sql = ""

            # Calculate the last parameter index for top_k
            top_k_param_idx = 1 + len(filter_params) + 1

            query_sql = f"""
                SELECT unique_id, workspace_id, content, metadata, vector::text,
                       1 - (vector <=> $1::vector) AS score
                FROM "{table_name}"
                {where_sql}
                ORDER BY vector <=> $1::vector
                LIMIT ${top_k_param_idx}
                """

            rows = await conn.fetch(query_sql, query_vector_str, *filter_params, top_k)

            nodes: List[VectorNode] = []
            for row in rows:
                unique_id = row["unique_id"]
                workspace_id_col = row["workspace_id"]
                content = row["content"]
                metadata = row["metadata"]
                vector_str = row["vector"]
                score = row["score"]

                # Parse vector string (format: [0.1,0.2,0.3] from pgvector)
                vector = json.loads(vector_str)

                # Parse metadata if it's a string
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                elif metadata is None:
                    metadata = {}

                node = VectorNode(
                    unique_id=unique_id,
                    workspace_id=workspace_id_col or workspace_id,
                    content=content,
                    metadata=metadata,
                    vector=vector,
                )
                node.metadata["score"] = float(score)
                nodes.append(node)

            return nodes
        else:
            # Filter-only search without vector similarity
            if filter_params:
                where_sql = f"WHERE {where_clause}"
                top_k_param_idx = len(filter_params) + 1
            else:
                where_sql = ""
                top_k_param_idx = 1

            query_sql = f"""
                SELECT unique_id, workspace_id, content, metadata, vector::text
                FROM "{table_name}"
                {where_sql}
                LIMIT ${top_k_param_idx}
                """

            rows = await conn.fetch(query_sql, *filter_params, top_k)

            nodes: List[VectorNode] = []
            for row in rows:
                unique_id = row["unique_id"]
                workspace_id_col = row["workspace_id"]
                content = row["content"]
                metadata = row["metadata"]
                vector_str = row["vector"]

                # Parse vector string
                vector = json.loads(vector_str)

                # Parse metadata if it's a string
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                elif metadata is None:
                    metadata = {}

                node = VectorNode(
                    unique_id=unique_id,
                    workspace_id=workspace_id_col or workspace_id,
                    content=content,
                    metadata=metadata,
                    vector=vector,
                )
                nodes.append(node)

            return nodes

    # ==================== Insert Methods ====================

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, **kwargs):
        """Insert vector nodes into the PostgreSQL table.

        Args:
            nodes: A single VectorNode or list of VectorNodes to insert.
            workspace_id: The identifier of the workspace to insert into.
            **kwargs: Additional keyword arguments (unused).
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]
        now_embedded_nodes = self.get_node_embeddings(not_embedded_nodes)

        table_name = self._get_table_name(workspace_id)
        all_nodes = embedded_nodes + now_embedded_nodes

        # Use batch insert with ON CONFLICT for upsert
        with self._conn.cursor() as cur:
            for i in range(0, len(all_nodes), self.batch_size):
                batch = all_nodes[i : i + self.batch_size]
                values = []
                for node in batch:
                    # pgvector accepts list directly or string format
                    vector_value = node.vector
                    if isinstance(vector_value, list):
                        # Convert list to string format for pgvector: '[0.1,0.2,0.3]'
                        vector_str = "[" + ",".join(str(v) for v in vector_value) + "]"
                    else:
                        vector_str = str(vector_value)

                    values.append(
                        (
                            node.unique_id,
                            workspace_id,
                            node.content,
                            json.dumps(node.metadata),
                            vector_str,
                        ),
                    )

                # Use INSERT ... ON CONFLICT for upsert
                cur.executemany(
                    f"""
                    INSERT INTO "{table_name}" (unique_id, workspace_id, content, metadata, vector)
                    VALUES (%s, %s, %s, %s, %s::vector)
                    ON CONFLICT (unique_id) DO UPDATE SET
                        workspace_id = EXCLUDED.workspace_id,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        vector = EXCLUDED.vector
                    """,
                    values,
                )

            self._conn.commit()
        logger.info(f"insert nodes.size={len(all_nodes)} into workspace_id={workspace_id}")

    async def async_insert(
        self,
        nodes: VectorNode | List[VectorNode],
        workspace_id: str,
        **kwargs,
    ):
        """Insert vector nodes into the PostgreSQL table (async).

        Args:
            nodes: A single VectorNode or list of VectorNodes to insert.
            workspace_id: The identifier of the workspace to insert into.
            **kwargs: Additional keyword arguments (unused).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]

        # Use async embedding
        now_embedded_nodes = await self.async_get_node_embeddings(not_embedded_nodes)

        table_name = self._get_table_name(workspace_id)
        all_nodes = embedded_nodes + now_embedded_nodes

        conn = await self._get_async_conn()

        # Use batch insert with ON CONFLICT for upsert
        for i in range(0, len(all_nodes), self.batch_size):
            batch = all_nodes[i : i + self.batch_size]

            # Prepare batch data for executemany
            batch_data = []
            for node in batch:
                # pgvector accepts list directly or string format
                vector_value = node.vector
                if isinstance(vector_value, list):
                    # Convert list to string format for pgvector: '[0.1,0.2,0.3]'
                    vector_str = "[" + ",".join(str(v) for v in vector_value) + "]"
                else:
                    vector_str = str(vector_value)

                batch_data.append(
                    (
                        node.unique_id,
                        workspace_id,
                        node.content,
                        json.dumps(node.metadata),
                        vector_str,
                    ),
                )

            # Use executemany for batch insert
            await conn.executemany(
                f"""
                INSERT INTO "{table_name}" (unique_id, workspace_id, content, metadata, vector)
                VALUES ($1, $2, $3, $4, $5::vector)
                ON CONFLICT (unique_id) DO UPDATE SET
                    workspace_id = EXCLUDED.workspace_id,
                    content = EXCLUDED.content,
                    metadata = EXCLUDED.metadata,
                    vector = EXCLUDED.vector
                """,
                batch_data,
            )

        logger.info(f"async insert nodes.size={len(all_nodes)} into workspace_id={workspace_id}")

    # ==================== Delete Methods ====================

    def delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Delete vector nodes from the PostgreSQL table.

        Args:
            node_ids: A single node ID or list of node IDs to delete.
            workspace_id: The identifier of the workspace to delete from.
            **kwargs: Additional keyword arguments (unused).
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        table_name = self._get_table_name(workspace_id)
        with self._conn.cursor() as cur:
            cur.executemany(
                f'DELETE FROM "{table_name}" WHERE unique_id = %s',
                [(node_id,) for node_id in node_ids],
            )
            self._conn.commit()
        logger.info(f"delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, **kwargs):
        """Delete vector nodes from the PostgreSQL table (async).

        Args:
            node_ids: A single node ID or list of node IDs to delete.
            workspace_id: The identifier of the workspace to delete from.
            **kwargs: Additional keyword arguments (unused).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        table_name = self._get_table_name(workspace_id)
        conn = await self._get_async_conn()

        # Use batch delete with ANY for better performance
        await conn.execute(
            f'DELETE FROM "{table_name}" WHERE unique_id = ANY($1)',
            node_ids,
        )

        logger.info(f"async delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    # ==================== Close Methods ====================

    def close(self):
        """Close the synchronous PostgreSQL connection."""
        if self._conn:
            self._conn.close()

    async def async_close(self):
        """Close the asynchronous PostgreSQL connection."""
        if self._async_conn:
            await self._async_conn.close()
            self._async_conn = None

    # ==================== Private Async Helper Methods ====================

    async def _get_async_conn(self):
        """Get or create async PostgreSQL connection."""
        if self._async_conn is None:
            import asyncpg

            logger.debug(f"Establishing async PostgreSQL connection: {self._async_conn_string}")
            self._async_conn = await asyncpg.connect(self._async_conn_string)
            logger.debug("Async PostgreSQL connection established successfully")
        return self._async_conn
