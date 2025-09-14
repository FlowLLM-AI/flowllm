from mcp.types import CallToolResult

from flowllm.client.mcp_client import McpClient
from flowllm.context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall, ParamAttrs


class BaseMcpOp(BaseAsyncToolOp):

    def __init__(self, mcp_name: str = "", tool_name: str = "", save_answer: bool = True, **kwargs):
        self.mcp_name: str = mcp_name
        self.tool_name: str = tool_name
        super().__init__(save_answer=save_answer, **kwargs)

    def build_tool_call(self) -> ToolCall:
        tool_call_dict = C.external_mcp_tool_call_dict[self.mcp_name]
        tool_call: ToolCall = tool_call_dict[self.tool_name]
        tool_call.output_schema = {
            f"{self.name}_result": ParamAttrs(type="str", description=f"The execution result of the {self.name}")
        }
        return tool_call

    async def async_execute(self):
        mcp_server_config = C.service_config.external_mcp[self.mcp_name]
        async with McpClient(name=self.mcp_name, config=mcp_server_config) as client:
            result: CallToolResult = await client.call_tool(self.tool_name, arguments=self.input_dict)
            self.set_result(result.content[0].text)
