from loguru import logger
from mcp.types import CallToolResult

from flowllm.client.mcp_client import McpClient
from flowllm.context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall, ParamAttrs


@C.register_op(register_app="FlowLLM")
class BaseMcpOp(BaseAsyncToolOp):

    def __init__(self,
                 mcp_name: str = "",
                 tool_name: str = "",
                 save_answer: bool = True,
                 clear_required: bool = False,
                 **kwargs):

        self.mcp_name: str = mcp_name
        self.tool_name: str = tool_name
        self.clear_required: bool = clear_required
        super().__init__(save_answer=save_answer, **kwargs)
        # https://bailian.console.aliyun.com/?tab=mcp#/mcp-market

    def build_tool_call(self) -> ToolCall:
        tool_call_dict = C.external_mcp_tool_call_dict[self.mcp_name]
        tool_call: ToolCall = tool_call_dict[self.tool_name]

        if self.clear_required:
            for name, attr in tool_call.input_schema.items():
                attr.required = False

        tool_call.output_schema = {
            f"{self.name}_result": ParamAttrs(type="str", description=f"The execution result of the {self.name}")
        }
        return tool_call

    async def async_execute(self):
        mcp_server_config = C.service_config.external_mcp[self.mcp_name]
        async with McpClient(name=self.mcp_name, config=mcp_server_config) as client:
            result: CallToolResult = await client.call_tool(self.tool_name, arguments=self.input_dict)
            logger.info(f"{self.mcp_name}@{self.tool_name} result: {result}")
            self.set_result(result.content[0].text)
