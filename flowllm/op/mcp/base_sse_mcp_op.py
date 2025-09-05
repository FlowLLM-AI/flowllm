from fastmcp import Client
from mcp.types import CallToolResult

from flowllm.context import C
from flowllm.op import BaseToolOp
from flowllm.schema.tool_call import ToolCall


class BaseSSEMcpOp(BaseToolOp):

    def __init__(self, host: str = "", tool_name: str = "", **kwargs):
        self.host: str = host
        self.tool_name: str = tool_name
        super().__init__(**kwargs)

    def build_tool_call(self) -> ToolCall:
        key = f"{self.host}/{self.tool_name}"
        assert key in C.sse_mcp_dict, \
            f"host={self.host} tool_name={self.tool_name} not found in mcp_tool_call_dict"
        return C.sse_mcp_dict[key]

    def default_execute(self):
        self.context.response.answer = self.output_dict[f"{self.name}_result"] = f"{self.name} execute failed!"

    async def async_execute(self):
        async with Client(f"{self.host}/sse/") as client:
            result: CallToolResult = await client.call_tool(self.tool_name, arguments=self.input_dict)
        self.context.response.answer = self.output_dict[f"{self.name}_result"] = result.content[0].text
