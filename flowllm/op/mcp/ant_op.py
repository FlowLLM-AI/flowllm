import asyncio
import json
import os

from flowllm.context import FlowContext, C
from flowllm.op.mcp.base_sse_mcp_op import BaseSSEMcpOp


@C.register_op()
class AntSearchOp(BaseSSEMcpOp):

    def __init__(self, **kwargs):
        host = os.getenv("FLOW_MCP_HOSTS", "").split(",")[0]
        super().__init__(host=host, tool_name="search", **kwargs)


@C.register_op()
class AntInvestmentOp(BaseSSEMcpOp):

    def __init__(self, **kwargs):
        host = os.getenv("FLOW_MCP_HOSTS", "").split(",")[0]
        super().__init__(host=host, tool_name="investment_analysis", **kwargs)


async def async_main():
    op = AntSearchOp()
    context = FlowContext(query="阿里巴巴怎么样？", entity="阿里巴巴")
    await op.async_call(context=context)
    print(json.dumps(op.tool_call.simple_input_dump(), ensure_ascii=False))
    print(context.response.answer)

    op = AntInvestmentOp()
    context = FlowContext(entity="阿里巴巴", analysis_category="股票")
    await op.async_call(context=context)
    print(json.dumps(op.tool_call.simple_input_dump(), ensure_ascii=False))
    print(context.response.answer)


if __name__ == "__main__":
    C.prepare_sse_mcp().set_service_config().init_by_service_config()

    asyncio.run(async_main())
