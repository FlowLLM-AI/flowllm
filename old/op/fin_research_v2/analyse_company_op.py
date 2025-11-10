import asyncio

from loguru import logger

from flowllm import BaseAsyncToolOp
from flowllm.enumeration.role import Role
from flowllm.op.crawl import Crawl4aiOp
from flowllm.schema.message import Message
from flowllm.schema.tool_call import ToolCall


class AnalyseCompanyOp(BaseAsyncToolOp):
    file_path: str = __file__

    def __init__(
        self,
        llm: str = "qwen3_max_instruct",
        # llm: str = "qwen3_30b_instruct",
        # llm: str = "qwen3_80b_instruct",
        # llm: str = "qwen25_max_instruct",
        **kwargs,
    ):
        super().__init__(llm=llm, **kwargs)

    def build_tool_call(self) -> ToolCall:
        return ToolCall(
            **{
                "description": "...",
                "input_schema": {
                    "name": {
                        "type": "string",
                        "description": "公司名称",
                        "required": True,
                    },
                },
            },
        )

    async def async_execute(self):
        name = self.input_dict["name"]

        # search_op = self.ops[0]
        # assert isinstance(search_op, BaseAsyncToolOp)
        # await search_op.async_call(query=f"{name} 财报内容")
        #
        #
        # messages = [
        #     Message(role=Role.SYSTEM, content="你是一位金融专家\n\n" + str(search_op.output)),
        #     Message(role=Role.USER, content=f"分析{name}公司，从营收和利润的角度分析哪些是核心业务，json返回，只返回核心业务名称和营收/l利润占比"),
        # ]
        # assistant_message = await self.llm.achat(messages=messages, enable_stream_print=True)
        # print(assistant_message)

        # search_op = self.ops[0]
        # assert isinstance(search_op, BaseAsyncToolOp)
        # await search_op.async_call(query=f"{name} 财报内容")

        # search_op = self.ops[0]
        # assert isinstance(search_op, BaseAsyncToolOp)
        # await search_op.async_call(query=f"{name} 财报内容")

        messages = [
            # Message(role=Role.SYSTEM, content="你是一位金融专家\n\n" + str(search_op.output)),
            Message(role=Role.SYSTEM, content="你是一位金融专家"),
            # Message(role=Role.USER, content=f"分析{name}的黄金业务，哪些因子会影响估值，如何影响"),
            Message(
                role=Role.USER,
                content=f"哪些因子会影响**小米汽车**的估值，请先一步步思考，输出思考内容，然后使用json的格式回答，每一个影响的因子要包含因子名称，影响机制，按照重要度排序，最多3个",
            ),
        ]
        assistant_message = await self.llm.achat(messages=messages, enable_stream_print=True)
        print(assistant_message)

        self.set_result("123")


async def main():
    from flowllm.app import FlowLLMApp
    from flowllm.op.search.mcp_search_op import TongyiMcpSearchOp

    async with FlowLLMApp(args=["config=fin_research"]):
        test_cases = [
            "紫金矿业",
            # "中国平安",
        ]

        for name in test_cases:
            logger.info(f"\n{'=' * 60}\n测试: {name}\n{'=' * 60}")
            op = AnalyseCompanyOp() << TongyiMcpSearchOp()
            await op.async_call(name=name)
            logger.info(f"\n最终结果:\n{op.output}")


if __name__ == "__main__":
    asyncio.run(main())
