from typing import List, Optional

from mcp.types import CallToolResult

from flowllm.client.mcp_client import McpClient
from flowllm.context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class BaseMcpOp(BaseAsyncToolOp):
    """
    Base class for MCP (Model Context Protocol) tool operations.

    Extends BaseAsyncToolOp to integrate with external MCP servers.
    MCP is a protocol for connecting LLMs to external tools and data sources.

    This class:
    - Loads tool schemas from configured MCP servers
    - Allows modifying tool schemas (required/optional/deleted parameters)
    - Executes tool calls via MCP client
    - Supports timeout and retry logic

    MCP servers are configured in service config and discovered at runtime.
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
        """
        Initialize an MCP tool operation.

        Args:
            mcp_name: Name of the MCP server (as configured in service config)
            tool_name: Name of the tool on that MCP server
            save_answer: Whether to save result to context.response.answer
            input_schema_required: List of parameters to mark as required (override)
            input_schema_optional: List of parameters to mark as optional (override)
            input_schema_deleted: List of parameters to remove from schema
            max_retries: Number of retry attempts (default 3 for MCP)
            timeout: Timeout in seconds for MCP calls
            raise_exception: Whether to raise exceptions or use default behavior
            **kwargs: Additional parameters passed to BaseAsyncToolOp
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
        """
        Build tool schema from MCP server's tool definition with optional modifications.

        Loads the tool schema from the global MCP tool registry and applies
        any schema modifications (required/optional/deleted parameters).

        Returns:
            Modified ToolCall schema for this MCP tool
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
        """
        Execute the MCP tool call via MCP client.

        Creates an MCP client connection, calls the tool with input parameters,
        and stores the result. The client is automatically closed after execution.
        """
        mcp_server_config = C.service_config.external_mcp[self.mcp_name]
        async with McpClient(
            name=self.mcp_name,
            config=mcp_server_config,
            max_retries=self.max_retries,
            timeout=self.timeout,
        ) as client:
            result: CallToolResult = await client.call_tool(self.tool_name, arguments=self.input_dict)
            self.set_result(result.content[0].text)
