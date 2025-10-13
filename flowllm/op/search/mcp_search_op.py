import asyncio

from flowllm.context import FlowContext, C
from flowllm.op.base_mcp_op import BaseMcpOp


@C.register_op(register_app="FlowLLM")
class TongyiMcpSearchOp(BaseMcpOp):

    def __init__(self, **kwargs):
        kwargs["mcp_name"] = "tongyi_search"
        kwargs["tool_name"] = "bailian_web_search"
        kwargs["save_answer"] = True
        kwargs["input_schema_optional"] = ["count"]
        kwargs["input_schema_deleted"] = ["ctx"]
        # kwargs.setdefault("timeout", 10.0)
        super().__init__(**kwargs)


@C.register_op(register_app="FlowLLM")
class BochaMcpSearchOp(BaseMcpOp):

    def __init__(self, **kwargs):
        kwargs["mcp_name"] = "bochaai_search"
        kwargs["tool_name"] = "bocha_web_search"
        kwargs["save_answer"] = True
        kwargs["input_schema_optional"] = ["freshness", "count"]
        kwargs["input_schema_deleted"] = ["ctx"]
        # kwargs.setdefault("timeout", 10.0)
        super().__init__(**kwargs)


async def main():
    from flowllm.app import FlowLLMApp
    async with FlowLLMApp(args=["config=fin_research"]):
        op = TongyiMcpSearchOp()
        await op.async_call(context=FlowContext(query="what is ai?"))
        print("tongyi:", op.output)

        op = BochaMcpSearchOp()
        await op.async_call(context=FlowContext(query="what is ai?"))
        print("bocha:", op.output)


if __name__ == "__main__":
    asyncio.run(main())
