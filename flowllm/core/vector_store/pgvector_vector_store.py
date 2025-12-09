"""PostgreSQL pgvector vector store implementation.

This module provides a PostgreSQL-based vector store that stores vector nodes
in PostgreSQL tables using the pgvector extension. It supports workspace management,
vector similarity search, metadata filtering using SQL WHERE clauses, and provides
both synchronous and asynchronous operations using psycopg and asyncpg.
"""

import os
from typing import List, Tuple, Iterable, Dict, Any, Optional

from loguru import logger

from .local_vector_store import LocalVectorStore
from ..context import C
from ..schema import VectorNode


@C.register_vector_store("pgvector")
class PgVectorStore(LocalVectorStore):
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
            **kwargs: Additional keyword arguments passed to LocalVectorStore.
        """
        super().__init__(**kwargs)
        self.connection_string = connection_string or os.getenv(
            "FLOW_PGVECTOR_CONNECTION_STRING", "postgresql://localhost/postgres"
        )
        self.async_connection_string = async_connection_string or os.getenv(
            "FLOW_PGVECTOR_ASYNC_CONNECTION_STRING"
        )
        self.batch_size = batch_size

        # Initialize synchronous connection
        import psycopg

        self._conn = psycopg.connect(self.connection_string)
        self._conn.autocommit = False

        # Initialize async connection if async_connection_string is provided
        self._async_conn = None
        if self.async_connection_string:
            import asyncpg

            # We'll create the async connection lazily in async methods
            self._async_conn_string = self.async_connection_string
        else:
            # Convert sync connection string to asyncpg format
            if self.connection_string.startswith("postgresql://"):
                self._async_conn_string = self.connection_string.replace(
                    "postgresql://", "postgresql+asyncpg://", 1
                )
            else:
                self._async_conn_string = self.connection_string

        # Ensure pgvector extension exists
        with self._conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self._conn.commit()

        logger.info(
            f"PostgreSQL pgvector client initialized with connection_string={self.connection_string}"
        )

    def _get_table_name(self, workspace_id: str) -> str:
        """Get the table name for a workspace.

        Args:
            workspace_id: The workspace identifier.

        Returns:
            str: The table name (sanitized workspace_id).
        """
        # Sanitize workspace_id to be a valid PostgreSQL identifier
        # Replace non-alphanumeric characters with underscores
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", workspace_id)
        return f"workspace_{sanitized}"

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
                """
            )
            # Create index for vector similarity search
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS "{table_name}_vector_idx"
                ON "{table_name}" USING ivfflat (vector vector_cosine_ops)
                WITH (lists = 100)
                """
            )
            # Create index for metadata filtering
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS "{table_name}_metadata_idx"
                ON "{table_name}" USING gin (metadata)
                """
            )
            self._conn.commit()
        logger.info(f"Created workspace table: {table_name} with vector({dimensions})")

    def list_workspace(self, **kwargs) -> List[str]:
        """
        List all existing workspaces (tables) in PostgreSQL.

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
                """
            )
            table_names = [row[0] for row in cur.fetchall()]
            # Remove 'workspace_' prefix
            workspace_ids = [name.replace("workspace_", "", 1) for name in table_names]
            return workspace_ids

    def iter_workspace_nodes(
        self,
        workspace_id: str,
        max_size: int = 10000,
        **kwargs,
    ) -> Iterable[VectorNode]:
        """Iterate over all nodes in a workspace.

        Args:
            workspace_id: The identifier of the workspace to iterate over.
            max_size: Maximum number of nodes to retrieve (default: 10000).
            **kwargs: Additional keyword arguments (unused).

        Yields:
            VectorNode: Vector nodes from the workspace.
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        table_name = self._get_table_name(workspace_id)
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
                yield node

    def refresh(self, workspace_id: str):
        """Refresh is not needed for PostgreSQL, but kept for API compatibility.

        Args:
            workspace_id: The identifier of the workspace (unused).
        """
        # PostgreSQL doesn't need explicit refresh like Elasticsearch
        pass

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
        import json

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
    def _build_sql_filters(filter_dict: Optional[Dict[str, Any]] = None, use_async: bool = False) -> Tuple[str, List[Any]]:
        """Build SQL WHERE clause from filter_dict.

        Converts a filter dictionary into SQL WHERE conditions.
        Supports both term filters (exact match) and range filters (gte, lte, gt, lt).

        Args:
            filter_dict: Dictionary of filter conditions. Keys are metadata field names,
                values can be exact match values or range dictionaries like
                {"gte": 1, "lte": 10}.
            use_async: If True, use asyncpg-style placeholders ($1, $2), else use psycopg-style (%s).

        Returns:
            Tuple[str, List[Any]]: SQL WHERE clause string and list of parameters.
        """
        if not filter_dict:
            return "", []

        conditions = []
        params = []
        param_idx = 1
        placeholder = "$%d" if use_async else "%s"

        for key, filter_value in filter_dict.items():
            # Handle nested keys by using JSONB path operators
            jsonb_path = f"metadata->>'{key}'"

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

    def search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity.

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model.
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

        query_vector = self.embedding_model.get_embeddings(query)

        # Build filters from filter_dict
        where_clause, filter_params = self._build_sql_filters(filter_dict)

        table_name = self._get_table_name(workspace_id)
        where_sql = f"WHERE {where_clause}" if where_clause else ""

        # Use cosine distance (<=>) for similarity search
        # Cosine similarity = 1 - cosine distance
        # Convert query_vector to string format for pgvector
        query_vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        
        with self._conn.cursor() as cur:
            # Parameter order in SQL: SELECT %s::vector, WHERE %s..., ORDER BY %s::vector, LIMIT %s
            # So parameters should be: [query_vector_str] + filter_params + [query_vector_str, top_k]
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
                import json

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
                node.metadata["score"] = float(score)
                nodes.append(node)

            return nodes

    def insert(self, nodes: VectorNode | List[VectorNode], workspace_id: str, refresh: bool = True, **kwargs):
        """Insert vector nodes into the PostgreSQL table.

        Args:
            nodes: A single VectorNode or list of VectorNodes to insert.
            workspace_id: The identifier of the workspace to insert into.
            refresh: Whether to refresh after insertion (default: True, kept for API compatibility).
            **kwargs: Additional keyword arguments (unused).
        """
        if not self.exist_workspace(workspace_id=workspace_id):
            self.create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]
        now_embedded_nodes = self.embedding_model.get_node_embeddings(not_embedded_nodes)

        table_name = self._get_table_name(workspace_id)
        all_nodes = embedded_nodes + now_embedded_nodes

        # Use batch insert with ON CONFLICT for upsert
        with self._conn.cursor() as cur:
            for i in range(0, len(all_nodes), self.batch_size):
                batch = all_nodes[i : i + self.batch_size]
                values = []
                for node in batch:
                    import json

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
                        )
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

    def delete(self, node_ids: str | List[str], workspace_id: str, refresh: bool = True, **kwargs):
        """Delete vector nodes from the PostgreSQL table.

        Args:
            node_ids: A single node ID or list of node IDs to delete.
            workspace_id: The identifier of the workspace to delete from.
            refresh: Whether to refresh after deletion (default: True, kept for API compatibility).
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

    # Async methods using asyncpg
    async def _get_async_conn(self):
        """Get or create async PostgreSQL connection."""
        if self._async_conn is None:
            import asyncpg

            # Parse connection string - asyncpg only supports postgresql:// format
            conn_str = self._async_conn_string
            if conn_str.startswith("postgresql+asyncpg://"):
                conn_str = conn_str.replace("postgresql+asyncpg://", "postgresql://", 1)
            elif not conn_str.startswith("postgresql://"):
                # If it doesn't start with postgresql://, assume it's a standard connection string
                pass

            logger.debug(f"Establishing async PostgreSQL connection: {conn_str}")
            self._async_conn = await asyncpg.connect(conn_str)
            logger.debug(f"Async PostgreSQL connection established successfully")
        return self._async_conn

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
            """
        )
        # Create index for vector similarity search
        await conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS "{table_name}_vector_idx"
            ON "{table_name}" USING ivfflat (vector vector_cosine_ops)
            WITH (lists = 100)
            """
        )
        # Create index for metadata filtering
        await conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS "{table_name}_metadata_idx"
            ON "{table_name}" USING gin (metadata)
            """
        )
        logger.info(f"Created workspace table: {table_name} with vector({dimensions})")

    async def async_refresh(self, workspace_id: str):
        """Refresh is not needed for PostgreSQL, but kept for API compatibility (async).

        Args:
            workspace_id: The identifier of the workspace (unused).
        """
        # PostgreSQL doesn't need explicit refresh like Elasticsearch
        pass

    async def async_search(
        self,
        query: str,
        workspace_id: str,
        top_k: int = 1,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> List[VectorNode]:
        """Search for similar vector nodes using cosine similarity (async).

        Args:
            query: The text query to search for. Will be embedded using the
                embedding model's async method.
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

        # Use async embedding
        query_vector = await self.embedding_model.get_embeddings_async(query)

        # Build filters from filter_dict (use asyncpg-style placeholders)
        where_clause, filter_params = self._build_sql_filters(filter_dict, use_async=True)

        table_name = self._get_table_name(workspace_id)
        where_sql = f"WHERE {where_clause}" if where_clause else ""

        conn = await self._get_async_conn()

        # Convert query_vector to string format for pgvector
        query_vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

        # Build parameter list: query_vector ($1), filter_params ($2, $3, ...), top_k ($last)
        # Need to adjust placeholder indices in where_clause if filter_params exist
        # WHERE clause appears after SELECT, so filter_params come after query_vector
        param_offset = 1  # $1 for query_vector, $2+ for filter_params
        if filter_params:
            # Adjust placeholder indices in where_clause
            adjusted_where = where_clause
            for i in range(len(filter_params)):
                old_placeholder = f"${i + 1}"
                new_placeholder = f"${param_offset + i + 1}"
                adjusted_where = adjusted_where.replace(old_placeholder, new_placeholder)
            where_sql = f"WHERE {adjusted_where}" if adjusted_where else ""
        
        # Calculate the last parameter index for top_k
        top_k_param_idx = 1 + len(filter_params) + 1  # $1 (query_vector) + filter_params + 1

        # Use cosine distance (<=>) for similarity search
        # Cosine similarity = 1 - cosine distance
        query_sql = f"""
            SELECT unique_id, workspace_id, content, metadata, vector::text,
                   1 - (vector <=> $1::vector) AS score
            FROM "{table_name}"
            {where_sql}
            ORDER BY vector <=> $1::vector
            LIMIT ${top_k_param_idx}
            """
        
        # Parameter order: query_vector ($1), filter_params ($2, $3, ...), top_k ($last)
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
            import json

            # pgvector returns vector as string like '[0.1,0.2,0.3]'
            vector = json.loads(vector_str)
            
            # Parse metadata if it's a string (asyncpg may return JSONB as string)
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

    async def async_insert(
        self,
        nodes: VectorNode | List[VectorNode],
        workspace_id: str,
        refresh: bool = True,
        **kwargs,
    ):
        """Insert vector nodes into the PostgreSQL table (async).

        Args:
            nodes: A single VectorNode or list of VectorNodes to insert.
            workspace_id: The identifier of the workspace to insert into.
            refresh: Whether to refresh after insertion (default: True, kept for API compatibility).
            **kwargs: Additional keyword arguments (unused).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            await self.async_create_workspace(workspace_id=workspace_id)

        if isinstance(nodes, VectorNode):
            nodes = [nodes]

        embedded_nodes = [node for node in nodes if node.vector]
        not_embedded_nodes = [node for node in nodes if not node.vector]

        # Use async embedding
        now_embedded_nodes = await self.embedding_model.get_node_embeddings_async(not_embedded_nodes)

        table_name = self._get_table_name(workspace_id)
        all_nodes = embedded_nodes + now_embedded_nodes

        conn = await self._get_async_conn()

        # Use batch insert with ON CONFLICT for upsert
        for i in range(0, len(all_nodes), self.batch_size):
            batch = all_nodes[i : i + self.batch_size]
            for node in batch:
                import json

                # pgvector accepts list directly or string format
                vector_value = node.vector
                if isinstance(vector_value, list):
                    # Convert list to string format for pgvector: '[0.1,0.2,0.3]'
                    vector_str = "[" + ",".join(str(v) for v in vector_value) + "]"
                else:
                    vector_str = str(vector_value)

                await conn.execute(
                    f"""
                    INSERT INTO "{table_name}" (unique_id, workspace_id, content, metadata, vector)
                    VALUES ($1, $2, $3, $4, $5::vector)
                    ON CONFLICT (unique_id) DO UPDATE SET
                        workspace_id = EXCLUDED.workspace_id,
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        vector = EXCLUDED.vector
                    """,
                    node.unique_id,
                    workspace_id,
                    node.content,
                    json.dumps(node.metadata),
                    vector_str,
                )

        logger.info(f"async insert nodes.size={len(all_nodes)} into workspace_id={workspace_id}")

    async def async_delete(self, node_ids: str | List[str], workspace_id: str, refresh: bool = True, **kwargs):
        """Delete vector nodes from the PostgreSQL table (async).

        Args:
            node_ids: A single node ID or list of node IDs to delete.
            workspace_id: The identifier of the workspace to delete from.
            refresh: Whether to refresh after deletion (default: True, kept for API compatibility).
            **kwargs: Additional keyword arguments (unused).
        """
        if not await self.async_exist_workspace(workspace_id=workspace_id):
            logger.warning(f"workspace_id={workspace_id} does not exist!")
            return

        if isinstance(node_ids, str):
            node_ids = [node_ids]

        table_name = self._get_table_name(workspace_id)
        conn = await self._get_async_conn()

        for node_id in node_ids:
            await conn.execute(f'DELETE FROM "{table_name}" WHERE unique_id = $1', node_id)

        logger.info(f"async delete node_ids.size={len(node_ids)} from workspace_id={workspace_id}")

    def close(self):
        """Close the synchronous PostgreSQL connection."""
        if self._conn:
            self._conn.close()

    async def async_close(self):
        """Close the asynchronous PostgreSQL connection."""
        if self._async_conn:
            await self._async_conn.close()
            self._async_conn = None

