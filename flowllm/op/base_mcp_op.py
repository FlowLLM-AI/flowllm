from typing import List, Optional

from mcp.types import CallToolResult

from flowllm.client.mcp_client import McpClient
from flowllm.context import C
from flowllm.op.base_async_tool_op import BaseAsyncToolOp
from flowllm.schema.tool_call import ToolCall


@C.register_op(register_app="FlowLLM")
class BaseMcpOp(BaseAsyncToolOp):

    def __init__(self,
                 mcp_name: str = "",
                 tool_name: str = "",
                 save_answer: bool = True,
                 input_schema_required: List[str] = None,
                 input_schema_optional: List[str] = None,
                 input_schema_deleted: List[str] = None,
                 max_retries: int = 3,
                 timeout: Optional[float] = None,
                 raise_exception: bool = False,
                 **kwargs):

        self.mcp_name: str = mcp_name
        self.tool_name: str = tool_name
        self.input_schema_required: List[str] = input_schema_required
        self.input_schema_optional: List[str] = input_schema_optional
        self.input_schema_deleted: List[str] = input_schema_deleted
        self.timeout: Optional[float] = timeout
        super().__init__(save_answer=save_answer, max_retries=max_retries, raise_exception=raise_exception, **kwargs)
        # https://bailian.console.aliyun.com/?tab=mcp#/mcp-market

    def build_tool_call(self) -> ToolCall:
        tool_call_dict = C.external_mcp_tool_call_dict[self.mcp_name]
        tool_call: ToolCall = tool_call_dict[self.tool_name].model_copy(deep=True)

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
        mcp_server_config = C.service_config.external_mcp[self.mcp_name]
        async with McpClient(name=self.mcp_name, config=mcp_server_config, 
                            max_retries=self.max_retries, timeout=self.timeout) as client:
            result: CallToolResult = await client.call_tool(self.tool_name, arguments=self.input_dict)
            self.set_result(result.content[0].text)
