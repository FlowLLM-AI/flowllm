"""MCP web search operation module.

This module provides tool operations for performing web searches using MCP (Model Context Protocol).
It enables LLM models to retrieve relevant information from the internet by executing
search queries through different MCP search providers.
"""

from ...core.context import C
from ...core.op import BaseMcpOp


@C.register_op()
class TongyiMcpSearchOp(BaseMcpOp):
    """A tool operation for performing web searches using Tongyi MCP.

    This operation enables LLM models to search the internet for information by
    providing search keywords through the Tongyi search MCP server. It uses the
    bailian_web_search tool to execute search queries.

    Attributes:
        mcp_name: The MCP server name (default: "tongyi_search").
        tool_name: The tool name to call (default: "bailian_web_search").
        save_answer: Whether to save the search answer (default: True).
        input_schema_optional: Optional input schema fields (default: ["count"]).
        input_schema_deleted: Deleted input schema fields (default: ["ctx"]).
    """

    def __init__(self, **kwargs):
        kwargs.update(
            {
                "mcp_name": "tongyi_search",
                "tool_name": "bailian_web_search",
                "save_answer": True,
                "input_schema_optional": ["count"],
                "input_schema_deleted": ["ctx"],
            },
        )
        super().__init__(**kwargs)


@C.register_op()
class BochaMcpSearchOp(BaseMcpOp):
    """A tool operation for performing web searches using BochaAI MCP.

    This operation enables LLM models to search the internet for information by
    providing search keywords through the BochaAI search MCP server. It uses the
    bocha_web_search tool to execute search queries with support for freshness
    and count parameters.

    Attributes:
        mcp_name: The MCP server name (default: "bochaai_search").
        tool_name: The tool name to call (default: "bocha_web_search").
        save_answer: Whether to save the search answer (default: True).
        input_schema_optional: Optional input schema fields (default: ["freshness", "count"]).
        input_schema_deleted: Deleted input schema fields (default: ["ctx"]).
    """

    def __init__(self, **kwargs):
        kwargs.update(
            {
                "mcp_name": "bochaai_search",
                "tool_name": "bocha_web_search",
                "save_answer": True,
                "input_schema_optional": ["freshness", "count"],
                "input_schema_deleted": ["ctx"],
            },
        )
        super().__init__(**kwargs)
