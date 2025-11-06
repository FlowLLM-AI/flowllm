"""Base operator for calling external MCP tools asynchronously.

This module defines `BaseMcpOp`, which leverages `BaseAsyncToolOp` to fetch the
tool schema from a configured MCP provider and execute the tool via
`FastMcpClient`. It supports overriding input parameter requirements and
propagates inputs/outputs through the shared context managed by the base class.
"""

from typing import List, Optional

from .base_async_tool_op import BaseAsyncToolOp
from ..context import C
from ..schema import ToolCall
from ..utils import FastMcpClient


@C.register_op()
class BaseMcpOp(BaseAsyncToolOp):
    """Async op that invokes an external MCP tool.

    The tool's `ToolCall` schema is loaded from `C.external_mcp_tool_call_dict`
    using `mcp_name` and `tool_name`. Inputs are prepared by the base class and
    passed to the MCP server; results are written back to the context.
    """

    def __init__(
        self,
        mcp_name: str = "",
        tool_name: str = "",
        save_answer: bool = True,
        input_schema_required: List[str] = None,
        input_schema_optional: List[str] = None,
        input_schema_deleted: List[str] = None,
        max_retries: int = 3,
        timeout: Optional[float] = None,
        raise_exception: bool = False,
        **kwargs,
    ):
        """Initialize the MCP operator.

        Args:
            mcp_name: The MCP server name configured in service config.
            tool_name: The MCP tool name to call on the server.
            save_answer: Whether to save primary output to `response.answer`.
            input_schema_required: Parameter names to force as required.
            input_schema_optional: Parameter names to force as optional.
            input_schema_deleted: Parameter names to remove from input schema.
            max_retries: Max retries for MCP client calls.
            timeout: Optional timeout (seconds) for the MCP request.
            raise_exception: Whether to raise when execution fails.
            **kwargs: Forwarded to `BaseAsyncToolOp` / `BaseAsyncOp`.
        """
        self.mcp_name: str = mcp_name
        self.tool_name: str = tool_name
        self.input_schema_required: List[str] = input_schema_required
        self.input_schema_optional: List[str] = input_schema_optional
        self.input_schema_deleted: List[str] = input_schema_deleted
        self.timeout: Optional[float] = timeout
        super().__init__(save_answer=save_answer, max_retries=max_retries, raise_exception=raise_exception, **kwargs)
        # Example MCP marketplace: https://bailian.console.aliyun.com/?tab=mcp#/mcp-market

    def build_tool_call(self) -> ToolCall:
        """Build the `ToolCall` for this MCP tool, applying overrides.

        Returns:
            ToolCall: A deep-copied tool schema with requirement overrides and
            deletions applied as configured.
        """
        tool_call_dict = C.external_mcp_tool_call_dict[self.mcp_name]
        tool_call: ToolCall = tool_call_dict[self.tool_name].model_copy(deep=True)

        # Override parameter requirements if specified
        if self.input_schema_required:
            for name in self.input_schema_required:
                tool_call.input_schema[name].required = True

        if self.input_schema_optional:
            for name in self.input_schema_optional:
                tool_call.input_schema[name].required = False

        if self.input_schema_deleted:
            for name in self.input_schema_deleted:
                tool_call.input_schema.pop(name, None)

        return tool_call

    async def async_execute(self):
        """Execute the MCP tool call and store the result.

        Uses `FastMcpClient` with configured retries and timeout, invokes the
        tool with `self.input_dict`, then writes the returned value via
        `set_result` so that post-execution hooks can persist it to context.
        """
        mcp_server_config = C.service_config.external_mcp[self.mcp_name]
        async with FastMcpClient(
            name=self.mcp_name,
            config=mcp_server_config,
            max_retries=self.max_retries,
            timeout=self.timeout,
        ) as client:
            result: str = await client.call_tool(self.tool_name, arguments=self.input_dict)
            self.set_output(result)
